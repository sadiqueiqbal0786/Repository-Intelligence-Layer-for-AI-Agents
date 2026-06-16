"""``repointel serve`` — Phase 5 MCP server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

# stdout is reserved for the MCP stdio transport; all status goes to stderr.
console = Console(stderr=True)


def serve(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to serve intelligence for.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Run the RepoIntel MCP server (stdio) so AI agents can query the repo."""
    from repointel.mcp.server import run

    console.print(f"[dim]RepoIntel MCP server · {Path(path).resolve()}[/]")
    run(path)
