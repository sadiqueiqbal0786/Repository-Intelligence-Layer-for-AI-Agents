"""Tests for Phase 2 repository scanning + JSON storage."""

from __future__ import annotations

from pathlib import Path

from repointel.scanners import resolve_project_root, scan_repo
from repointel.storage.json import read_repository, repository_path, write_repository


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _python_repo(root: Path) -> None:
    _write(
        root,
        "pyproject.toml",
        """
[project]
name = "demo"
dependencies = ["fastapi>=0.110", "pydantic>=2"]

[project.optional-dependencies]
test = ["pytest>=8"]

[project.scripts]
demo = "demo.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    )
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/main.py", "def main():\n    return 1\n")
    _write(root, "src/demo/cli.py", "app = None\n")
    _write(root, "README.md", "# demo\n")
    # Noise that must be ignored.
    _write(root, "node_modules/x/index.js", "x")
    _write(root, ".venv/lib/y.py", "y = 1")


def test_inventory_counts(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)

    # 4 indexed files: pyproject.toml, 3 .py under src/demo, README.md => actually 5
    paths = {f.path for f in inv.files}
    assert "pyproject.toml" in paths
    assert "src/demo/main.py" in paths
    assert "README.md" in paths
    # Ignored trees excluded.
    assert not any(p.startswith("node_modules") for p in paths)
    assert not any(p.startswith(".venv") for p in paths)

    assert inv.file_count == len(inv.files)
    assert inv.fingerprint.framework == "FastAPI"


def test_module_discovery(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)

    module_paths = {m.path for m in inv.modules}
    assert "src/demo" in module_paths
    demo = next(m for m in inv.modules if m.path == "src/demo")
    assert demo.language == "Python"
    assert demo.file_count == 3  # __init__, main, cli


def test_dependencies_extracted(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)

    by_name = {d.name: d for d in inv.dependencies}
    assert "fastapi" in by_name
    assert by_name["fastapi"].version == ">=0.110"
    assert by_name["fastapi"].dev is False
    # optional-dependencies are marked dev.
    assert by_name["pytest"].dev is True


def test_entry_points_and_configs(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)

    assert "src/demo/main.py" in inv.entry_points
    assert any(e.startswith("demo = ") for e in inv.entry_points)
    assert "pyproject.toml" in inv.configs


def test_secrets_are_never_indexed(tmp_path: Path) -> None:
    """Secret-bearing files (.env, keys, credentials) must not enter memory,
    which can be committed/shared. Value-free templates stay."""
    _python_repo(tmp_path)
    _write(tmp_path, ".env", "API_KEY=super-secret-value\n")
    _write(tmp_path, ".env.production", "DB_PASSWORD=hunter2\n")
    _write(tmp_path, ".env.example", "API_KEY=\n")
    _write(tmp_path, "certs/server.key", "-----BEGIN PRIVATE KEY-----\n")
    _write(tmp_path, "id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----\n")
    inv = scan_repo(tmp_path)

    indexed = {f.path for f in inv.files}
    assert ".env" not in indexed
    assert ".env.production" not in indexed
    assert "certs/server.key" not in indexed
    assert "id_rsa" not in indexed
    # The template carries structure, not secrets — keep it.
    assert ".env.example" in indexed
    assert ".env" not in inv.configs
    assert ".env.production" not in inv.configs


def test_loc_counted(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)
    assert inv.total_loc > 0
    main = next(f for f in inv.files if f.path == "src/demo/main.py")
    assert main.loc == 2
    assert main.language == "Python"


def test_flutter_dependencies(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pubspec.yaml",
        """
name: app
dependencies:
  flutter:
    sdk: flutter
  go_router: ^14.0.0
dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
""",
    )
    _write(tmp_path, "lib/main.dart", "void main() {}\n")

    inv = scan_repo(tmp_path)
    by_name = {d.name: d for d in inv.dependencies}
    assert by_name["go_router"].version == "^14.0.0"
    assert by_name["go_router"].dev is False
    assert by_name["build_runner"].dev is True
    assert "flutter" in by_name  # nested SDK form parsed, version absent
    assert by_name["flutter"].version is None
    assert "lib/main.dart" in inv.entry_points


def test_flutter_native_dirs_ignored(tmp_path: Path) -> None:
    """A Flutter app's vendored native trees must not swamp the Dart source."""
    _write(tmp_path, "pubspec.yaml", "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n")
    _write(tmp_path, "lib/main.dart", "void main() {}\n")
    _write(tmp_path, "lib/widgets/home.dart", "class Home {}\n")
    # Vendored / native noise that must be excluded.
    _write(tmp_path, "ios/Pods/Firebase/firebase.c", "int x;\n")
    _write(tmp_path, "ios/.symlinks/plugins/foo/foo.swift", "let x = 1\n")
    _write(tmp_path, "ios/Flutter/ephemeral/engine.cpp", "int y;\n")
    _write(tmp_path, ".fvm/flutter_sdk/engine/core.cc", "int z;\n")

    inv = scan_repo(tmp_path)
    paths = {f.path for f in inv.files}

    assert "lib/main.dart" in paths
    assert not any("Pods" in p or ".symlinks" in p or "ephemeral" in p for p in paths)
    assert not any(p.startswith(".fvm") for p in paths)
    # Dart is the only source language counted -> it's the primary language.
    assert inv.fingerprint.language == "Dart"
    assert set(inv.fingerprint.languages) == {"Dart"}


def test_resolve_project_root(tmp_path: Path) -> None:
    # Manifest at the given path -> unchanged (normal repo, zero behavior change).
    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    assert resolve_project_root(tmp_path) == tmp_path


def test_resolve_project_root_nested(tmp_path: Path) -> None:
    # No root manifest, exactly one subdir has one -> descend into it.
    _write(tmp_path, "README.md", "# monorepo\n")
    _write(tmp_path, "app/pubspec.yaml", "name: app\n")
    assert resolve_project_root(tmp_path) == tmp_path / "app"


def test_resolve_project_root_ambiguous_stays(tmp_path: Path) -> None:
    # Several candidate subdirs -> don't guess, stay at the given path.
    _write(tmp_path, "a/pubspec.yaml", "name: a\n")
    _write(tmp_path, "b/package.json", "{}\n")
    assert resolve_project_root(tmp_path) == tmp_path


def test_scan_detects_nested_flutter_project(tmp_path: Path) -> None:
    """Pointing at a repo whose Flutter app lives under app/ analyzes app/."""
    _write(tmp_path, "README.md", "# monorepo\n")
    _write(
        tmp_path,
        "app/pubspec.yaml",
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n  go_router: ^14.0.0\n",
    )
    _write(tmp_path, "app/lib/main.dart", "void main() {}\n")

    inv = scan_repo(tmp_path)

    assert inv.path == str(tmp_path / "app")  # resolved into the nested project
    assert inv.fingerprint.language == "Dart"
    assert inv.fingerprint.framework == "Flutter"
    paths = {f.path for f in inv.files}
    assert "lib/main.dart" in paths  # relative to the resolved root, not the repo root
    assert "go_router" in {d.name for d in inv.dependencies}


def test_storage_round_trip(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    inv = scan_repo(tmp_path)

    out = write_repository(inv, tmp_path)
    assert out == repository_path(tmp_path)
    assert out.exists()

    loaded = read_repository(tmp_path)
    assert loaded is not None
    assert loaded.file_count == inv.file_count
    assert loaded.fingerprint.framework == "FastAPI"
    assert {d.name for d in loaded.dependencies} == {d.name for d in inv.dependencies}


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_repository(tmp_path) is None


def test_dart_subfolder_pubspec_is_detected(tmp_path: Path) -> None:
    """A Flutter app under app/ in a MONOREPO (root has a sibling package, so
    the analysis stays at the repo root) must still be detected: framework,
    package manager, state management, databases, and dependencies all come
    from the subfolder pubspec — which used to be missed entirely."""
    _write(tmp_path, "server/pyproject.toml", '[project]\nname = "server"\n')
    _write(tmp_path, "server/main.py", "x = 1\n")
    _write(
        tmp_path,
        "app/pubspec.yaml",
        "name: app\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
        "  flutter_bloc: ^9.0.0\n"
        "  cloud_firestore: ^5.0.0\n"
        "dev_dependencies:\n"
        "  flutter_test:\n"
        "    sdk: flutter\n",
    )
    _write(tmp_path, "app/lib/main.dart", "void main() {}\n")
    inv = scan_repo(tmp_path)

    fp = inv.fingerprint
    assert fp.framework == "Flutter"
    assert fp.package_manager == "pub"
    assert fp.state_management == "BLoC"
    assert "Cloud Firestore" in fp.databases

    dep_names = {d.name for d in inv.dependencies}
    assert {"flutter_bloc", "cloud_firestore", "flutter_test"} <= dep_names
    assert "app/lib/main.dart" in inv.entry_points


def test_generated_dart_files_excluded_from_source_metrics(tmp_path: Path) -> None:
    """Generated files stay listed but don't count as source: zero LOC, no
    language, and not counted as a module's source file."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(tmp_path, "lib/user.dart", "class User {}\n" * 5)          # 5 LOC of real code
    _write(tmp_path, "lib/user.freezed.dart", "class _$U {}\n" * 900)  # 900 LOC of codegen
    _write(tmp_path, "lib/user.g.dart", "x\n" * 500)
    inv = scan_repo(tmp_path)

    by_path = {f.path: f for f in inv.files}
    # Still listed as files…
    assert "lib/user.freezed.dart" in by_path
    # …but non-source: no language, zero LOC.
    assert by_path["lib/user.freezed.dart"].language is None
    assert by_path["lib/user.freezed.dart"].loc == 0
    assert by_path["lib/user.g.dart"].loc == 0
    # total_loc counts only the hand-written file, not the ~1400 generated lines.
    assert inv.total_loc == 5
    # The lib module reports a single source file, not three.
    lib = next(m for m in inv.modules if m.path == "lib")
    assert lib.file_count == 1
