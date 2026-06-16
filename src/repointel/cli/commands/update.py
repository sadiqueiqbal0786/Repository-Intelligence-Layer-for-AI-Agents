"""``repointel update`` — Phase 7 incremental intelligence."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.context.incremental import ChangeSet, update_memory
from repointel.context.memory import persist_memory

console = Console()

_MAX_LISTED = 10


def update(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to update.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Update repository memory, re-analyzing only the files that changed."""
    bundle, changes = update_memory(path)
    persist_memory(bundle, Path(bundle.repo.path))

    repo = bundle.repo
    console.print(f"\n[bold cyan]RepoIntel update[/] · [dim]{repo.name}[/]")

    if changes.full_rebuild:
        console.print("  [yellow]No cache found[/] — built full repository memory.")
    elif not changes.has_changes:
        console.print("  [green]Up to date[/] — no source changes since last build.")
    else:
        _render_changes(changes)

    console.print(
        f"  graph: {repo.node_count} nodes, {repo.edge_count} edges · "
        f"{repo.file_count} files\n"
    )
    console.print("[green]✓[/] Repository memory refreshed.")


def _render_changes(changes: ChangeSet) -> None:
    rows = [
        ("[green]added[/]", changes.added),
        ("[yellow]modified[/]", changes.modified),
        ("[red]deleted[/]", changes.deleted),
    ]
    for label, paths in rows:
        if not paths:
            continue
        console.print(f"  {label} ({len(paths)}):")
        for p in paths[:_MAX_LISTED]:
            console.print(f"    [dim]{p}[/]")
        if len(paths) > _MAX_LISTED:
            console.print(f"    [dim]… and {len(paths) - _MAX_LISTED} more[/]")
    console.print(f"  [dim]{changes.unchanged} files reused from cache[/]")
