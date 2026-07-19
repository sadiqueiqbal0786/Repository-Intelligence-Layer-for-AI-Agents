"""Tests for the live staleness (build-commit drift) check."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from repointel.context.memory import build_memory
from repointel.context.staleness import assess_staleness


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _git_env() -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": "Tester",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "Tester",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "PATH": os.environ.get("PATH", ""),
    }


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=_git_env())


def test_staleness_non_git_is_never_stale(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/a.py", "x = 1\n")
    bundle = build_memory(tmp_path)
    assert bundle.repo.built_at_commit is None
    fresh = assess_staleness(tmp_path, bundle.repo.built_at_commit)
    assert fresh["is_git"] is False
    assert fresh["stale"] is False


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_memory_is_stamped_and_drift_detected(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "src/demo/a.py", "x = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    bundle = build_memory(tmp_path)
    assert bundle.repo.built_at_commit  # stamped with HEAD

    # Fresh right after build.
    fresh = assess_staleness(tmp_path, bundle.repo.built_at_commit)
    assert fresh["is_git"] is True
    assert fresh["stale"] is False
    assert fresh["changed_files"] == 0

    # Change a file -> memory is now stale.
    _write(tmp_path, "src/demo/a.py", "x = 1\ny = 2\n")
    drifted = assess_staleness(tmp_path, bundle.repo.built_at_commit)
    assert drifted["stale"] is True
    assert drifted["changed_files"] >= 1
    assert "repointel update" in drifted["message"]
