"""``repointel graph`` — Phase 3 architecture graph."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repointel.graph.builder import build_graph
from repointel.scanners import scan_repo
from repointel.storage.json import write_graph

console = Console()


def graph(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to graph.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the full graph as JSON instead of a summary."
    ),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write .repointel/graph.json."),
) -> None:
    """Build the architecture graph (nodes + relationships) → .repointel/graph.json."""
    inventory = scan_repo(path)
    # scan_repo may resolve a nested project root; graph from the same path.
    arch = build_graph(Path(inventory.path), inventory)

    if as_json:
        console.print_json(arch.model_dump_json(indent=2))
        return

    console.print(f"[green]✓[/] {arch.node_count} nodes, {arch.edge_count} edges\n")

    table = Table(title="Nodes", title_style="bold", show_header=True, header_style="dim")
    table.add_column("Kind")
    table.add_column("Count", justify="right")
    for kind, count in sorted(arch.node_kinds.items(), key=lambda kv: -kv[1]):
        table.add_row(kind, str(count))
    console.print(table)

    edges = Table(title="Edges", title_style="bold", show_header=True, header_style="dim")
    edges.add_column("Kind")
    edges.add_column("Count", justify="right")
    for kind, count in sorted(arch.edge_kinds.items(), key=lambda kv: -kv[1]):
        edges.add_row(kind, str(count))
    console.print(edges)

    if not no_save:
        out = write_graph(arch, Path(arch.path))
        try:
            shown = out.relative_to(Path(arch.path))
        except ValueError:
            shown = out
        console.print(f"\n[dim]Saved to[/] {shown}")
