"""``repointel eval`` — measure answer accuracy alongside token cost.

Runs the self-contained accuracy suite (a fixture whose answers are known by
construction) and prints a scorecard. This is the benchmark that proves the
product: a high token-reduction number means nothing if the answers are wrong.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def eval(  # noqa: A001 - the user-facing subcommand name is "eval" by design
    repo: Path = typer.Option(
        None,
        "--repo",
        help="Also print a token/confidence field report for a real repo.",
    ),
) -> None:
    """Run the accuracy eval (fixture with known answers) and report accuracy +
    tokens. Add --repo PATH for a real-repo token/confidence field report."""
    from repointel.context.eval import build_reference_repo, run_eval

    with tempfile.TemporaryDirectory() as tmp:
        root = build_reference_repo(Path(tmp))
        report = run_eval(root)

    table = Table(title="RepoIntel accuracy eval", show_lines=False)
    table.add_column("check")
    table.add_column("question")
    table.add_column("result")
    for r in report.results:
        mark = "[green]PASS[/]" if r.passed else "[red]FAIL[/]"
        table.add_row(r.name, r.question, f"{mark}  [dim]{r.detail}[/]")
    console.print(table)

    if report.accuracy == 1.0:
        acc_color = "green"
    elif report.accuracy >= 0.75:
        acc_color = "yellow"
    else:
        acc_color = "red"
    console.print(
        f"\nAccuracy: [{acc_color}]{report.passed}/{report.total} "
        f"({report.accuracy:.0%})[/]  ·  context pack: {report.context_tokens} tokens "
        f"vs {report.raw_tokens} raw ([bold]{report.token_reduction}×[/] reduction)"
    )
    if report.accuracy < 1.0:
        console.print("[dim]Failing checks are the backlog — fix or add coverage.[/]")

    if repo is not None:
        _field_report(repo)


def _field_report(repo: Path) -> None:
    from repointel.mcp import tools

    health = tools.get_health(repo)
    console.print(
        f"\n[bold]Field report[/] · {Path(repo).resolve()}\n"
        f"  confidence: {health.get('confidence')}  ·  "
        f"connectivity: {health.get('connectivity')}  ·  "
        f"isolated files: {health.get('isolated_files')}"
    )
    for warning in health.get("warnings", []):
        console.print(f"  [yellow]⚠[/] {warning}")
