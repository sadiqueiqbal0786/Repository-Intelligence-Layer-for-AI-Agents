"""CLI layer — the delivery mechanism (Typer).

The Typer ``app`` is assembled here from command modules under
:mod:`repointel.cli.commands`. The package entry point is ``repointel.cli:app``.
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from repointel import __version__
from repointel.cli.commands import analyze as analyze_command
from repointel.cli.commands import build as build_command
from repointel.cli.commands import graph as graph_command
from repointel.cli.commands import scan as scan_command

app = typer.Typer(
    name="repointel",
    help="Repository Intelligence Engine — build a persistent memory layer for your codebase.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# Register commands.
app.command()(analyze_command.analyze)
app.command()(scan_command.scan)
app.command()(graph_command.graph)
app.command()(build_command.build)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"repointel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(  # noqa: UP045 - Typer needs Optional at runtime
        None,
        "--version",
        "-V",
        help="Show the RepoIntel version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """RepoIntel root command. Run a subcommand to do useful work."""


__all__ = ["app"]
