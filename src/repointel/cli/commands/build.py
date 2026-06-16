"""``repointel build`` — Phase 4 repository memory."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.context.memory import build_memory, persist_memory
from repointel.models import Conventions

console = Console()


def build(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to build memory for.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Build the full repository memory under .repointel/ (the agent source of truth)."""
    bundle = build_memory(path)
    written = persist_memory(bundle, Path(bundle.repo.path))

    repo = bundle.repo
    console.print(f"\n[bold cyan]RepoIntel memory[/] · [dim]{repo.name}[/]")
    console.print(
        f"  {repo.file_count} files · {repo.module_count} modules · "
        f"{repo.dependency_count} deps · {repo.total_loc} LOC"
    )
    console.print(f"  graph: {repo.node_count} nodes, {repo.edge_count} edges\n")

    _render_conventions(bundle.conventions)

    console.print("[green]✓[/] Wrote repository memory:")
    base = Path(bundle.repo.path)
    for out in written:
        try:
            shown = out.relative_to(base)
        except ValueError:
            shown = out
        console.print(f"    [dim]{shown}[/]")


def _render_conventions(conv: Conventions) -> None:
    """Show the headline conventions discovered for the repo (Phase 6)."""
    rows: list[tuple[str, str | None]] = [
        ("Architecture", conv.architecture),
        ("Source layout", conv.source_layout),
        ("File naming", conv.naming.files),
        ("Class naming", conv.naming.classes),
        ("Function naming", conv.naming.functions),
        ("Dependency injection", conv.dependency_injection),
        ("Testing", conv.testing.framework),
        ("Layering", ", ".join(conv.layering) if conv.layering else None),
        ("Patterns", ", ".join(conv.patterns) if conv.patterns else None),
    ]
    shown = [(label, value) for label, value in rows if value]
    if not shown:
        return
    console.print("[bold]Conventions[/]")
    for label, value in shown:
        console.print(f"  [dim]{label}:[/] [green]{value}[/]")
    console.print()
