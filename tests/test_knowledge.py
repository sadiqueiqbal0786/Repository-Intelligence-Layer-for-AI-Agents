"""Tests for the Phase 11 knowledge layer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repointel.context.knowledge import (
    discover_decisions,
    project_history,
    record_decision,
)
from repointel.context.memory import build_memory, persist_memory
from repointel.storage.json import read_knowledge


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _project(root: Path) -> None:
    _write(root, "pyproject.toml", '[project]\nname = "demo"\ndependencies = ["fastapi>=0.110"]\n')
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(
        root,
        "src/demo/repository.py",
        "from demo.models import User\n\n\nclass UserRepository:\n    pass\n",
    )


_ADR = """# 1. Use SQLite for local storage

## Status

Accepted

## Context

We need a zero-config embedded store for the memory layer.

## Decision

Use SQLite via the standard library.
"""


def test_patterns_inferred_from_conventions(tmp_path: Path) -> None:
    _project(tmp_path)
    knowledge = build_memory(tmp_path).knowledge
    kinds = {p.kind for p in knowledge.patterns}
    names = {p.name for p in knowledge.patterns}
    assert "architecture" in kinds
    assert "FastAPI" in names  # dependency-injection pattern
    assert any(p.kind == "convention" for p in knowledge.patterns)


def test_adr_discovery(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "docs/adr/0001-use-sqlite.md", _ADR)

    decisions = discover_decisions(tmp_path)
    assert len(decisions) == 1
    d = decisions[0]
    assert d.title == "Use SQLite for local storage"
    assert d.status == "Accepted"
    assert d.source == "adr:docs/adr/0001-use-sqlite.md"
    assert d.context and "embedded store" in d.context


def test_adr_template_and_readme_skipped(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "docs/adr/README.md", "# Index\n")
    _write(tmp_path, "docs/adr/template.md", "# N. Title\n")
    _write(tmp_path, "docs/adr/0001-use-sqlite.md", _ADR)
    assert [d.id for d in discover_decisions(tmp_path)] == ["0001-use-sqlite"]


def test_record_decision_persists_and_survives_rebuild(tmp_path: Path) -> None:
    _project(tmp_path)
    persist_memory(build_memory(tmp_path), tmp_path)  # seed knowledge.json

    decision = record_decision(
        tmp_path, "Adopt the plugin architecture", rationale="extensibility"
    )
    assert decision.source == "manual"
    assert decision.id == "adopt-the-plugin-architecture"

    # A full rebuild must preserve the manually recorded decision.
    rebuilt = build_memory(tmp_path).knowledge
    manual = [d for d in rebuilt.decisions if d.source == "manual"]
    assert [d.title for d in manual] == ["Adopt the plugin architecture"]
    assert manual[0].rationale == "extensibility"


def test_record_decision_unique_ids(tmp_path: Path) -> None:
    _project(tmp_path)
    first = record_decision(tmp_path, "Same title")
    second = record_decision(tmp_path, "Same title")
    assert first.id != second.id
    assert read_knowledge(tmp_path) is not None


def test_history_non_git(tmp_path: Path) -> None:
    _project(tmp_path)
    history = project_history(tmp_path)
    assert history.is_git is False
    assert history.total_commits == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_history_from_git(tmp_path: Path) -> None:
    _project(tmp_path)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "Tester",
                "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "Tester",
                "GIT_COMMITTER_EMAIL": "t@example.com",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null",
                "PATH": __import__("os").environ.get("PATH", ""),
            },
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "Initial commit")

    history = project_history(tmp_path)
    assert history.is_git is True
    assert history.total_commits == 1
    assert history.contributor_count == 1
    assert history.top_contributors[0].name == "Tester"
    assert "Initial commit" in history.recent_commits
