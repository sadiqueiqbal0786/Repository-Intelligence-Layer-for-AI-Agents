"""``repointel impact`` — Phase 9 change-impact analysis."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.context.impact import analyze_impact, impact_candidates
from repointel.models import ImpactReport

console = Console()

_RISK_STYLE = {"high": "bold red", "medium": "yellow", "low": "green"}
_MAX_LISTED = 25


def impact(
    target: str = typer.Argument(
        ..., help="File path or name to assess (e.g. 'auth_service.py')."
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to the repository.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the report as JSON instead of a summary."
    ),
) -> None:
    """Predict the blast radius of changing a file — affected files, modules, and risk."""
    report = analyze_impact(path, target)

    if report is None:
        console.print(f"[red]No file matching[/] [bold]{target}[/].")
        candidates = impact_candidates(path, target)
        if candidates:
            console.print("\n[dim]Did you mean one of:[/]")
            for candidate in candidates:
                console.print(f"  [dim]{candidate}[/]")
        raise typer.Exit(code=1)

    if as_json:
        console.print_json(report.model_dump_json(indent=2))
        return

    _render(report)


def _render(report: ImpactReport) -> None:
    console.print(f"\n[bold cyan]Impact:[/] [bold]{report.file}[/]")

    style = _RISK_STYLE.get(report.risk_level, "white")
    console.print(f"[bold]Risk Level:[/] [{style}]{report.risk_level.upper()}[/]")
    console.print(f"[bold]Affected Files:[/] {report.affected_file_count}")

    _section("Affected Modules", report.affected_modules)
    _section("Directly importing files", report.direct_dependents)
    if report.dependencies:
        _section("This file depends on", report.dependencies)

    if report.risks:
        console.print("\n[bold]Notes[/]")
        for note in report.risks:
            console.print(f"  [dim]•[/] {note}")
    console.print()


def _section(title: str, items: list[str]) -> None:
    if not items:
        return
    console.print(f"\n[bold]{title}[/] ({len(items)})")
    for item in items[:_MAX_LISTED]:
        console.print(f"  [dim]•[/] {item}")
    if len(items) > _MAX_LISTED:
        console.print(f"  [dim]… and {len(items) - _MAX_LISTED} more[/]")


__all__ = ["impact"]
