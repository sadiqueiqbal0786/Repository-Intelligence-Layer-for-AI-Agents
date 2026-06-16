"""``repointel scan`` — Phase 2 repository inventory."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.scanners import scan_repo
from repointel.storage.json import write_repository

console = Console()


def scan(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to scan.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the full inventory as JSON instead of a summary."
    ),
    no_save: bool = typer.Option(
        False, "--no-save", help="Do not write .repointel/repository.json."
    ),
) -> None:
    """Index every file, module, and dependency into .repointel/repository.json."""
    inventory = scan_repo(path)

    if as_json:
        console.print_json(inventory.model_dump_json(indent=2))
        return

    console.print(f"[green]✓[/] {inventory.file_count} files indexed")
    console.print(f"[green]✓[/] {inventory.module_count} modules discovered")
    console.print(f"[green]✓[/] {inventory.dependency_count} dependencies found")
    if inventory.entry_points:
        console.print(f"[green]✓[/] {len(inventory.entry_points)} entry points located")

    if not no_save:
        out = write_repository(inventory, Path(inventory.path))
        try:
            shown = out.relative_to(Path(inventory.path))
        except ValueError:
            shown = out
        console.print(f"\n[dim]Saved to[/] {shown}")
