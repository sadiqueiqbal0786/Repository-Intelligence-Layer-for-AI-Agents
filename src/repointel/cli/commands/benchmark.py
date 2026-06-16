"""``repointel benchmark`` — Phase 12 token-savings benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from repointel.context.benchmark import benchmark_repos

console = Console()


def benchmark(
    paths: Optional[list[Path]] = typer.Argument(  # noqa: UP045 - Typer needs Optional at runtime
        None, help="Repositories to benchmark (defaults to the current directory)."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the results as JSON instead of a table."
    ),
) -> None:
    """Measure token savings: raw source tokens vs. context-pack tokens."""
    roots = paths or [Path(".")]
    results = benchmark_repos(roots)

    if as_json:
        console.print_json(json.dumps([r.model_dump() for r in results]))
        return

    table = Table(title="RepoIntel token-savings benchmark")
    table.add_column("Repo", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("LOC", justify="right")
    table.add_column("Raw tokens", justify="right")
    table.add_column("Pack tokens", justify="right")
    table.add_column("Ratio", justify="right", style="green")
    table.add_column("Time (s)", justify="right")

    total_saved = 0
    for r in results:
        total_saved += r.tokens_saved_est
        table.add_row(
            r.repo,
            f"{r.source_files:,}",
            f"{r.source_loc:,}",
            f"{r.raw_tokens_est:,}",
            f"{r.pack_tokens_est:,}",
            f"{r.compression_ratio:g}×",
            f"{r.analyze_seconds:g}",
        )
    console.print(table)
    console.print(
        f"\n[green]≈ {total_saved:,} tokens saved[/] vs. reading the raw source "
        "to understand these repositories."
    )


__all__ = ["benchmark"]
