"""``repointel knowledge`` / ``repointel decide`` — Phase 11 knowledge layer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from repointel.context.knowledge import record_decision
from repointel.context.memory import build_memory, persist_memory
from repointel.models import Knowledge
from repointel.scanners import resolve_project_root
from repointel.storage.json import read_knowledge

console = Console()


def _load(path: Path) -> Knowledge:
    path = resolve_project_root(Path(path))
    knowledge = read_knowledge(path)
    if knowledge is None:
        persist_memory(build_memory(path), path)
        knowledge = read_knowledge(path) or Knowledge()
    return knowledge


def knowledge(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the repository.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the knowledge layer as JSON instead of a report."
    ),
) -> None:
    """Show the repository's knowledge layer: decisions, patterns, and history."""
    know = _load(path)

    if as_json:
        console.print_json(know.model_dump_json(indent=2))
        return

    _render(know)


def decide(
    title: str = typer.Argument(..., help="The decision, e.g. 'Use SQLite for local storage'."),
    why: Optional[str] = typer.Option(  # noqa: UP045 - Typer needs Optional at runtime
        None, "--why", "-w", help="Rationale for the decision."
    ),
    status: str = typer.Option("accepted", "--status", "-s", help="Decision status."),
    path: Path = typer.Option(
        Path("."),
        "--path",
        "-p",
        help="Path to the repository.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Record an architecture decision into the durable knowledge layer."""
    decision = record_decision(resolve_project_root(path), title, status=status, rationale=why)
    console.print(
        f"[green]✓[/] Recorded decision [bold]{decision.id}[/] "
        f"([dim]{decision.status}[/]): {decision.title}"
    )


def _render(know: Knowledge) -> None:
    console.print("\n[bold cyan]Knowledge Layer[/]")

    console.print(f"\n[bold]Decisions[/] ({len(know.decisions)})")
    if not know.decisions:
        console.print("  [dim]none recorded — capture one with `repointel decide`[/]")
    for d in know.decisions:
        status = f" [dim]({d.status})[/]" if d.status else ""
        console.print(f"  [green]•[/] {d.title}{status} [dim]· {d.source}[/]")

    console.print(f"\n[bold]Patterns[/] ({len(know.patterns)})")
    for p in know.patterns:
        console.print(f"  [yellow]•[/] [bold]{p.name}[/] [dim]({p.kind})[/] — {p.description}")

    h = know.history
    console.print("\n[bold]History[/]")
    if not h.is_git:
        console.print("  [dim]not a git repository[/]")
    else:
        console.print(
            f"  {h.total_commits} commits · {h.contributor_count} contributors · "
            f"{h.first_commit_date or '?'} → {h.last_commit_date or '?'}"
        )
        if h.top_contributors:
            top = ", ".join(f"{c.name} ({c.commits})" for c in h.top_contributors)
            console.print(f"  [dim]top:[/] {top}")
    console.print()


__all__ = ["decide", "knowledge"]
