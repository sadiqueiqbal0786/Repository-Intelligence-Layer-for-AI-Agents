"""Tests for Phase 4 repository memory."""

from __future__ import annotations

from pathlib import Path

from repointel.context.memory import build_memory, load_memory, persist_memory
from repointel.storage.json import memory_dir


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _python_project(root: Path) -> None:
    _write(
        root,
        "pyproject.toml",
        '[project]\nname = "demo"\ndependencies = ["fastapi>=0.110"]\n'
        '[project.optional-dependencies]\ntest = ["pytest>=8"]\n',
    )
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class Base:\n    pass\n\n\nclass User(Base):\n    pass\n")
    _write(
        root,
        "src/demo/service.py",
        "from demo.models import User\n\n\ndef make():\n    return User()\n",
    )
    _write(root, "tests/test_demo.py", "def test_ok():\n    assert True\n")


def test_build_memory_bundle(tmp_path: Path) -> None:
    _python_project(tmp_path)
    bundle = build_memory(tmp_path)

    assert bundle.repo.name == tmp_path.name
    assert bundle.repo.fingerprint.framework == "FastAPI"
    assert bundle.repo.node_count > 0
    # Manifest lists all six artifacts.
    assert "repo.json" in bundle.repo.artifacts
    assert "graph.json" in bundle.repo.artifacts
    assert "conventions.json" in bundle.repo.artifacts


def test_architecture_summary(tmp_path: Path) -> None:
    _python_project(tmp_path)
    bundle = build_memory(tmp_path)
    arch = bundle.architecture

    assert arch.framework == "FastAPI"
    assert "Python" in arch.languages
    # models.py is imported by service.py -> a key file.
    assert "src/demo/models.py" in arch.key_files
    # src/demo grouped under the "demo" layer (src/ stripped).
    layer_names = {layer.name for layer in arch.layers}
    assert "demo" in layer_names


def test_modules_doc(tmp_path: Path) -> None:
    _python_project(tmp_path)
    bundle = build_memory(tmp_path)

    by_path = {m.path: m for m in bundle.modules.modules}
    assert "src/demo" in by_path
    demo = by_path["src/demo"]
    assert demo.classes == 2  # Base, User
    assert "src/demo/models.py" in demo.files
    assert demo.loc > 0


def test_conventions(tmp_path: Path) -> None:
    _python_project(tmp_path)
    bundle = build_memory(tmp_path)
    conv = bundle.conventions

    assert conv.source_layout == "src"
    assert conv.package_manager == "pip"
    assert conv.file_naming == "snake_case"
    assert conv.testing.framework == "pytest"
    assert conv.testing.test_dir == "tests"
    assert conv.testing.test_count == 1

    # Phase 6: identifier-casing inferred from the graph.
    assert conv.naming.files == "snake_case"
    assert conv.naming.classes == "PascalCase"  # Base, User
    assert conv.naming.functions == "snake_case"  # make, test_ok
    # FastAPI is a dependency -> dependency injection wiring.
    assert conv.dependency_injection == "FastAPI"
    assert "dependency_injection" in conv.patterns


def test_conventions_detects_layering_and_patterns(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/domain/entities.py", "class Order:\n    pass\n")
    _write(tmp_path, "src/demo/data/repositories.py", "class OrderRepository:\n    pass\n")
    _write(tmp_path, "src/demo/presentation/controllers.py", "class OrderController:\n    pass\n")

    conv = build_memory(tmp_path).conventions
    assert {"data", "domain", "presentation"} <= set(conv.layering)
    assert "repository_pattern" in conv.patterns
    assert "controller_layer" in conv.patterns


def test_persist_and_load(tmp_path: Path) -> None:
    _python_project(tmp_path)
    bundle = build_memory(tmp_path)
    written = persist_memory(bundle, tmp_path)

    # All seven memory artifacts + the internal incremental cache (Phase 7).
    names = {p.name for p in written}
    assert names == {
        "repository.json",
        "graph.json",
        "repo.json",
        "architecture.json",
        "modules.json",
        "conventions.json",
        "knowledge.json",
        "cache.json",
    }
    # cache.json is an optimization, not agent-facing memory: kept out of the manifest.
    assert "cache.json" not in bundle.repo.artifacts
    assert "knowledge.json" in bundle.repo.artifacts
    assert all(p.exists() for p in written)
    assert all(p.parent == memory_dir(tmp_path) for p in written)

    loaded = load_memory(tmp_path)
    assert loaded is not None
    assert loaded.repo.fingerprint.framework == "FastAPI"
    assert loaded.conventions.source_layout == "src"
    assert any(m.path == "src/demo" for m in loaded.modules.modules)


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_memory(tmp_path) is None
