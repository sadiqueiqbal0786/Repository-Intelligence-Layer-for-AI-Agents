"""``repointel context`` — Phase 12 compact context pack."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repointel.context.compression import context_pack, render_context_markdown

console = Console()


def context(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the pack as JSON instead of markdown."
    ),
) -> None:
    """Emit the compact context pack — a whole repo's understanding in a few thousand tokens."""
    pack = context_pack(path)
    if pack is None:
        console.print("[red]Could not build a context pack for[/] " + str(path))
        raise typer.Exit(code=1)

    if as_json:
        console.print_json(pack.model_dump_json(indent=2))
        return

    # Print raw markdown so it can be piped straight into an agent prompt.
    print(render_context_markdown(pack), end="")


__all__ = ["context"]
