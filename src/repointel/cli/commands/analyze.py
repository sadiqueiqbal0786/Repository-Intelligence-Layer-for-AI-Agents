"""``repointel analyze`` — Phase 1 repository fingerprinting."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repointel.models import Fingerprint
from repointel.scanners import fingerprint_repo

console = Console()


def analyze(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to analyze.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the fingerprint as JSON instead of a table."
    ),
) -> None:
    """Fingerprint a repository: language, framework, package manager, and more."""
    fp = fingerprint_repo(path)

    if as_json:
        console.print_json(fp.model_dump_json(indent=2))
        return

    _render_fingerprint(fp)


def _render_fingerprint(fp: Fingerprint) -> None:
    console.print(f"\n[bold cyan]RepoIntel[/] · [dim]{fp.path}[/]\n")

    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Field", style="bold")
    table.add_column("Value")

    rows: list[tuple[str, str | None]] = [
        ("Language", fp.language),
        ("Framework", fp.framework),
        ("Package Manager", fp.package_manager),
        ("Build System", fp.build_system),
        ("State Management", fp.state_management),
        ("Navigation", fp.navigation),
        ("Databases", ", ".join(fp.databases) if fp.databases else None),
        ("Architecture", fp.architecture),
    ]
    shown = 0
    for label, value in rows:
        if value:
            table.add_row(label, f"[green]{value}[/]")
            shown += 1
    console.print(table)

    if shown == 0:
        console.print("[yellow]No recognizable ecosystem detected.[/]")

    if fp.languages:
        breakdown = "  ".join(f"{lang} [dim]({n})[/]" for lang, n in fp.languages.items())
        console.print(f"\n[dim]Source files:[/] {breakdown}")
    console.print()
