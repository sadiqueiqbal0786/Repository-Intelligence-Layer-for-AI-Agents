"""Change-impact loader (Phase 9).

Thin wrapper that ensures repository memory exists, then runs the pure
graph-level :func:`repointel.graph.impact.compute_impact` for a target file.
"""

from __future__ import annotations

from pathlib import Path

from repointel.context.memory import build_memory, persist_memory
from repointel.graph.impact import candidate_files, compute_impact
from repointel.models import ImpactReport
from repointel.storage.json import read_graph, read_repo_summary


def analyze_impact(root: Path, target: str) -> ImpactReport | None:
    """Predict the impact of changing ``target``; builds memory on first use."""
    root = Path(root)
    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), root)
    graph = read_graph(root)
    if graph is None:
        return None
    return compute_impact(graph, target)


def impact_candidates(root: Path, target: str) -> list[str]:
    """Ambiguous file matches for ``target`` (for 'did you mean' diagnostics)."""
    graph = read_graph(Path(root))
    return candidate_files(graph, target) if graph else []


__all__ = ["analyze_impact", "impact_candidates"]
