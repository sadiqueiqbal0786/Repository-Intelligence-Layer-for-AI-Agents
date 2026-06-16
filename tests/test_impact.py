"""Tests for Phase 9 change-impact analysis."""

from __future__ import annotations

from pathlib import Path

from repointel.context.impact import analyze_impact, impact_candidates
from repointel.context.memory import build_memory
from repointel.graph.impact import compute_impact


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _chain_project(root: Path) -> None:
    """models <- repository <- service <- api  (a 4-deep import chain)."""
    _write(root, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(root, "src/demo/repository.py", "from demo.models import User\n")
    _write(root, "src/demo/service.py", "from demo.repository import User\n")
    _write(root, "src/demo/api.py", "from demo.service import User\n")
    _write(root, "src/demo/unrelated.py", "X = 1\n")


def _graph(root: Path):
    return build_memory(root).graph


def test_transitive_blast_radius(tmp_path: Path) -> None:
    _chain_project(tmp_path)
    report = compute_impact(_graph(tmp_path), "src/demo/models.py")
    assert report is not None
    # repository, service and api all transitively depend on models.
    assert set(report.affected_files) == {
        "src/demo/repository.py",
        "src/demo/service.py",
        "src/demo/api.py",
    }
    assert report.affected_file_count == 3
    # Only repository.py imports models.py directly.
    assert report.direct_dependents == ["src/demo/repository.py"]


def test_leaf_file_has_no_impact(tmp_path: Path) -> None:
    _chain_project(tmp_path)
    report = compute_impact(_graph(tmp_path), "src/demo/api.py")
    assert report is not None
    assert report.affected_file_count == 0
    assert report.risk_level == "low"
    assert any("isolated" in note for note in report.risks)


def test_dependencies_listed(tmp_path: Path) -> None:
    _chain_project(tmp_path)
    report = compute_impact(_graph(tmp_path), "service.py")
    assert report is not None
    assert report.dependencies == ["src/demo/repository.py"]


def test_affected_modules_span(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/core/base.py", "class Base:\n    pass\n")
    _write(tmp_path, "src/demo/web/views.py", "from demo.core.base import Base\n")
    _write(tmp_path, "src/demo/jobs/tasks.py", "from demo.core.base import Base\n")

    report = compute_impact(_graph(tmp_path), "base.py")
    assert report is not None
    assert set(report.affected_modules) == {"src/demo/web", "src/demo/jobs"}


def test_unknown_file_returns_none(tmp_path: Path) -> None:
    _chain_project(tmp_path)
    assert compute_impact(_graph(tmp_path), "nope.py") is None


def test_ambiguous_target_lists_candidates(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/a/models.py", "class A:\n    pass\n")
    _write(tmp_path, "src/demo/b/models.py", "class B:\n    pass\n")

    # Two files share the basename -> ambiguous, no single resolution.
    assert analyze_impact(tmp_path, "models.py") is None
    candidates = impact_candidates(tmp_path, "models.py")
    assert set(candidates) == {"src/demo/a/models.py", "src/demo/b/models.py"}


def test_analyze_impact_builds_memory_on_first_call(tmp_path: Path) -> None:
    _chain_project(tmp_path)
    report = analyze_impact(tmp_path, "models.py")
    assert report is not None
    assert report.affected_file_count == 3
