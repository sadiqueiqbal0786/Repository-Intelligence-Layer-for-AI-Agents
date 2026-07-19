"""Tests for the Phase 8 explanation engine."""

from __future__ import annotations

from pathlib import Path

from repointel.context.explanation import build_explanation, explain
from repointel.context.memory import build_memory


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _layered_project(root: Path) -> None:
    """models  <-  repository  <-  service  (a small dependency chain)."""
    _write(root, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(
        root,
        "src/demo/repository.py",
        "from demo.models import User\n\n\nclass UserRepository:\n"
        "    def get(self):\n        return User()\n",
    )
    _write(
        root,
        "src/demo/service.py",
        "from demo.repository import UserRepository\n\n\nclass UserService:\n"
        "    def __init__(self):\n        self.repo = UserRepository()\n",
    )


def _explain(root: Path, target: str):
    bundle = build_memory(root)
    return build_explanation(target, bundle.modules, bundle.graph, bundle.inventory)


def test_resolve_by_basename(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    exp = _explain(tmp_path, "demo")
    assert exp is not None
    assert exp.module == "src/demo"


def test_unknown_module_returns_none(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    assert _explain(tmp_path, "does-not-exist") is None


def test_purpose_and_key_classes(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    exp = _explain(tmp_path, "demo")
    assert exp is not None
    # Purpose is generated from structure + the Repository/Service naming role.
    assert "module" in exp.purpose.lower()
    assert {"User", "UserRepository", "UserService"} <= set(exp.key_classes)


def test_critical_files_ranks_most_imported(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    exp = _explain(tmp_path, "demo")
    assert exp is not None
    # models.py is imported by repository.py -> it's a critical file in the module.
    assert "src/demo/models.py" in exp.critical_files


def test_risk_assessment_present(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    exp = _explain(tmp_path, "demo")
    assert exp is not None
    assert exp.risk_level in {"low", "medium", "high"}
    assert exp.risks  # always at least one rationale line


def test_resolve_prefers_source_over_test_dir(tmp_path: Path) -> None:
    """A bare name matching both lib/ source and a test dir resolves to source."""
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/calendars/model.py", "class Calendar:\n    pass\n")
    _write(tmp_path, "test/calendars/model_test.py", "def test_it():\n    pass\n")
    exp = _explain(tmp_path, "calendars")
    assert exp is not None
    assert exp.module == "src/demo/calendars"
    assert "test" not in exp.module.split("/")


def test_resolve_prefers_shallowest_match(tmp_path: Path) -> None:
    """Among non-test matches, the most canonical (shallowest) path wins."""
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/models/user.py", "class User:\n    pass\n")
    _write(tmp_path, "src/demo/feature/models/order.py", "class Order:\n    pass\n")
    exp = _explain(tmp_path, "models")
    assert exp is not None
    assert exp.module == "src/demo/models"


def test_explain_loads_memory_on_first_call(tmp_path: Path) -> None:
    _layered_project(tmp_path)
    # No prior build/persist — explain() must build memory itself.
    exp = explain(tmp_path, "demo")
    assert exp is not None
    assert exp.module == "src/demo"
    assert exp.file_count >= 3
