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
from repointel.cli.commands import benchmark as benchmark_command
from repointel.cli.commands import build as build_command
from repointel.cli.commands import context as context_command
from repointel.cli.commands import explain as explain_command
from repointel.cli.commands import graph as graph_command
from repointel.cli.commands import impact as impact_command
from repointel.cli.commands import init as init_command
from repointel.cli.commands import knowledge as knowledge_command
from repointel.cli.commands import scan as scan_command
from repointel.cli.commands import serve as serve_command
from repointel.cli.commands import update as update_command

app = typer.Typer(
    name="repointel",
    help="Repository Intelligence Engine — build a persistent memory layer for your codebase.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# Register commands.
app.command()(init_command.init)
app.command()(analyze_command.analyze)
app.command()(scan_command.scan)
app.command()(graph_command.graph)
app.command()(build_command.build)
app.command()(update_command.update)
app.command()(explain_command.explain)
app.command()(impact_command.impact)
app.command()(knowledge_command.knowledge)
app.command()(knowledge_command.decide)
app.command()(context_command.context)
app.command()(benchmark_command.benchmark)
app.command()(serve_command.serve)


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
