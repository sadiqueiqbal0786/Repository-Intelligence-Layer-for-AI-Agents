"""``repointel explain`` — Phase 8 explanation engine."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.context.explanation import available_modules
from repointel.context.explanation import explain as explain_module
from repointel.models import ModuleExplanation

console = Console()

_RISK_STYLE = {"high": "bold red", "medium": "yellow", "low": "green"}


def explain(
    target: str = typer.Argument(..., help="Module path or name to explain (e.g. 'auth')."),
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
        False, "--json", help="Emit the explanation as JSON instead of a report."
    ),
) -> None:
    """Explain a module from repository memory — purpose, dependencies, consumers, risk."""
    result = explain_module(path, target)

    if result is None:
        console.print(f"[red]No module matching[/] [bold]{target}[/].")
        options = available_modules(path)
        if options:
            console.print("\n[dim]Available modules:[/]")
            for option in options:
                console.print(f"  [dim]{option}[/]")
        raise typer.Exit(code=1)

    if as_json:
        console.print_json(result.model_dump_json(indent=2))
        return

    _render(result)


def _render(exp: ModuleExplanation) -> None:
    console.print(f"\n[bold cyan]Module:[/] [bold]{exp.module}[/]")
    if exp.language:
        console.print(f"[dim]{exp.language} · {exp.file_count} files · {exp.loc} LOC[/]")

    console.print(f"\n[bold]Purpose[/]\n  {exp.purpose}")

    _section("Depends on", exp.dependencies)
    _section("Used by", exp.consumers)
    _section("Critical files", exp.critical_files)
    _section("Key classes", exp.key_classes)
    if exp.entry_points:
        _section("Entry points", exp.entry_points)

    style = _RISK_STYLE.get(exp.risk_level, "white")
    console.print(f"\n[bold]Risk[/] · [{style}]{exp.risk_level.upper()}[/]")
    for risk in exp.risks:
        console.print(f"  [dim]•[/] {risk}")
    console.print()


def _section(title: str, items: list[str]) -> None:
    if not items:
        return
    console.print(f"\n[bold]{title}[/]")
    for item in items:
        console.print(f"  [dim]•[/] {item}")


__all__ = ["explain"]
