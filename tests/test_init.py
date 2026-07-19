"""Tests for `repointel init` onboarding helpers."""

from __future__ import annotations

import json
from pathlib import Path

from repointel.cli.commands.init import (
    install_pre_commit_hook,
    write_gitignore,
    write_mcp_config,
)


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_mcp_config_created_and_merged(tmp_path: Path) -> None:
    # Pre-existing config with another server must be preserved.
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8"
    )
    cfg, added = write_mcp_config(tmp_path)
    assert added is True
    data = json.loads(cfg.read_text())
    assert "other" in data["mcpServers"]  # untouched
    assert data["mcpServers"]["repointel"]["args"][0] == "serve"

    # Idempotent: a second call doesn't duplicate or clobber.
    _, added_again = write_mcp_config(tmp_path)
    assert added_again is False


def test_gitignore_keeps_brief_and_ignores_blobs(tmp_path: Path) -> None:
    (tmp_path / ".repointel").mkdir()
    path = write_gitignore(tmp_path)
    body = path.read_text()
    assert "*.json" in body
    assert "!BRIEF.md" in body


def test_pre_commit_hook_installed_and_respects_existing(tmp_path: Path) -> None:
    assert install_pre_commit_hook(tmp_path) == "not-git"

    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    assert install_pre_commit_hook(tmp_path) == "installed"
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert "repointel update" in hook.read_text()

    # A foreign hook is never clobbered.
    hook.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    assert install_pre_commit_hook(tmp_path) == "exists-foreign"
    assert "echo mine" in hook.read_text()
