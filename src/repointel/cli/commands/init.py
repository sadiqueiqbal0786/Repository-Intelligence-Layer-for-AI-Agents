"""``repointel init`` — one-step onboarding.

Adoption friction kills dev tools more than missing features, and "build once,
reuse forever" only holds if the memory is present, fresh, and reachable. This
wires all of that up in one command:

- builds the memory,
- writes a small, human-readable **brief** that is meant to be committed (so
  every clone/agent gets memory instantly) while the heavy JSON blobs are
  git-ignored (they wreck diffs),
- registers the MCP server in ``.mcp.json`` (merging, never clobbering),
- installs a git pre-commit hook that incrementally refreshes memory on every
  commit, so ``.repointel`` never silently drifts.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from repointel.storage.json import memory_dir

console = Console()

_HOOK_MARKER = "# repointel-managed"
_HOOK_BODY = f"""#!/bin/sh
{_HOOK_MARKER}
# Keep repository memory fresh on every commit (incremental; fast).
command -v repointel >/dev/null 2>&1 && repointel update . >/dev/null 2>&1
exit 0
"""

# Committing the brief spreads memory to every clone; the JSON artifacts are
# rebuilt locally and would only add noise to diffs.
_GITIGNORE_BODY = """# Machine-built memory artifacts — rebuilt locally, noisy in diffs.
*.json
# Keep the small human-readable brief committed so agents get memory on clone.
!BRIEF.md
!.gitignore
"""


def init(
    path: Path = typer.Argument(Path("."), help="Repository to initialize."),
    no_hook: bool = typer.Option(False, "--no-hook", help="Skip installing the git hook."),
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Skip writing .mcp.json."),
) -> None:
    """Set up RepoIntel in a repo: build memory, write a committable brief, wire
    the MCP server, and install a refresh-on-commit hook."""
    from repointel.context.compression import context_pack, render_context_markdown
    from repointel.context.memory import build_memory, persist_memory
    from repointel.scanners import resolve_project_root
    from repointel.storage.json import read_repo_summary

    root = resolve_project_root(Path(path).resolve())
    console.print(f"[bold]Initializing RepoIntel[/] in {root}")

    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), root)
    console.print("  [green]✓[/] built memory (.repointel/)")

    pack = context_pack(root)
    if pack is not None:
        brief = write_brief(root, render_context_markdown(pack))
        console.print(f"  [green]✓[/] wrote committable brief → {brief.name}")
    write_gitignore(root)
    console.print("  [green]✓[/] .repointel/.gitignore (commit BRIEF.md, ignore blobs)")

    if not no_mcp:
        cfg, added = write_mcp_config(root)
        verb = "added" if added else "already present in"
        console.print(f"  [green]✓[/] MCP server {verb} {cfg.name}")

    if not no_hook:
        console.print(f"  {_hook_glyph(install_pre_commit_hook(root))}")

    console.print(
        "\n[bold]Done.[/] Commit "
        f"[cyan]{memory_dir(root).name}/BRIEF.md[/] to share memory; run "
        "[cyan]/mcp[/] in your agent to connect."
    )


def write_brief(root: Path, markdown: str) -> Path:
    """Write the human-readable brief (the committable slice of memory)."""
    target = memory_dir(root) / "BRIEF.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def write_gitignore(root: Path) -> Path:
    target = memory_dir(root) / ".gitignore"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_GITIGNORE_BODY, encoding="utf-8")
    return target


def write_mcp_config(root: Path) -> tuple[Path, bool]:
    """Merge a repointel server entry into ``.mcp.json``; never clobber others.

    Returns the config path and whether an entry was added (False if it already
    had one).
    """
    target = root / ".mcp.json"
    data: dict = {}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    servers = data.setdefault("mcpServers", {})
    if "repointel" in servers:
        return target, False
    servers["repointel"] = {"command": "repointel", "args": ["serve", str(root)]}
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target, True


def install_pre_commit_hook(root: Path) -> str:
    """Install a refresh-on-commit hook. Returns a status string.

    Never overwrites a hook we don't own: if a foreign pre-commit exists, we
    leave it and say so.
    """
    hooks_dir = root / ".git" / "hooks"
    if not (root / ".git").is_dir():
        return "not-git"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="ignore")
        if _HOOK_MARKER not in existing:
            return "exists-foreign"
    hook.write_text(_HOOK_BODY, encoding="utf-8")
    hook.chmod(0o755)
    return "installed"


def _hook_glyph(status: str) -> str:
    return {
        "installed": "[green]✓[/] installed pre-commit hook (memory refreshes on commit)",
        "exists-foreign": "[yellow]•[/] left existing pre-commit hook untouched "
        "(add `repointel update .` to it to keep memory fresh)",
        "not-git": "[dim]–[/] not a git repo; skipped the pre-commit hook",
    }.get(status, status)
