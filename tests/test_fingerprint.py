"""Tests for Phase 1 repository fingerprinting."""

from __future__ import annotations

from pathlib import Path

from repointel.scanners import fingerprint_repo


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_python_fastapi_uv(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        """
[project]
name = "demo"
dependencies = ["fastapi>=0.110", "sqlalchemy>=2", "asyncpg"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    )
    _write(tmp_path, "uv.lock", "# lock")
    _write(tmp_path, "src/demo/main.py", "print('hi')\n")

    fp = fingerprint_repo(tmp_path)

    assert fp.language == "Python"
    assert fp.framework == "FastAPI"
    assert fp.package_manager == "uv"
    assert fp.build_system == "Hatchling"
    assert "PostgreSQL" in fp.databases
    assert "SQLAlchemy" in fp.databases
    assert fp.evidence["framework"] == "dependency 'fastapi'"


def test_python_django_poetry(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[tool.poetry]\nname = "x"\n[tool.poetry.dependencies]\ndjango = "^5.0"\n',
    )
    _write(tmp_path, "app/models.py", "")

    fp = fingerprint_repo(tmp_path)

    assert fp.framework == "Django"
    assert fp.package_manager == "Poetry"


def test_flutter_riverpod_gorouter(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pubspec.yaml",
        """
name: myapp
environment:
  sdk: ">=3.0.0"
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.0
  go_router: ^14.0.0
  sqflite: ^2.3.0
""",
    )
    _write(tmp_path, "lib/features/auth/auth_page.dart", "// dart")
    _write(tmp_path, "lib/main.dart", "void main() {}")

    fp = fingerprint_repo(tmp_path)

    assert fp.language == "Dart"
    assert fp.framework == "Flutter"
    assert fp.package_manager == "pub"
    assert fp.state_management == "Riverpod"
    assert fp.navigation == "GoRouter"
    assert "SQLite" in fp.databases
    assert fp.architecture == "Feature Based"


def test_clean_architecture_detection(tmp_path: Path) -> None:
    _write(tmp_path, "pubspec.yaml", "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n")
    for layer in ("domain", "data", "presentation"):
        _write(tmp_path, f"lib/{layer}/file.dart", "// x")

    fp = fingerprint_repo(tmp_path)

    assert fp.architecture == "Clean Architecture"


def test_empty_repo_is_graceful(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# nothing here")

    fp = fingerprint_repo(tmp_path)

    assert fp.language is None
    assert fp.framework is None
    assert fp.databases == []


def test_ignored_dirs_excluded(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    _write(tmp_path, "main.py", "x = 1")
    # Noise that must not be counted.
    _write(tmp_path, "node_modules/pkg/index.js", "x")
    _write(tmp_path, ".venv/lib/thing.py", "x")

    fp = fingerprint_repo(tmp_path)

    assert fp.languages.get("JavaScript") is None
    assert fp.languages["Python"] == 1
