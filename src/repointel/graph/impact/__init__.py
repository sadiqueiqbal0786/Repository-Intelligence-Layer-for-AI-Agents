"""Change-impact analysis over the graph (Phase 9).

Given a file, walk the ``imports`` edges *backwards* to find every file that
would be affected by changing it — directly and transitively — then summarize
the spread (modules touched) into a risk level. Pure graph computation; the
loader that builds/reads memory lives in :mod:`repointel.context.impact`.
"""

from __future__ import annotations

from repointel.graph.builder import file_id
from repointel.graph.traversal import GraphView
from repointel.models import ArchitectureGraph, ImpactReport

# Risk thresholds, keyed off blast radius (affected files) and module spread.
_HIGH_FILES, _HIGH_MODULES = 10, 5
_MEDIUM_FILES, _MEDIUM_MODULES = 3, 2


def compute_impact(graph: ArchitectureGraph, target: str) -> ImpactReport | None:
    """Build an impact report for ``target``; ``None`` if it doesn't resolve."""
    file_paths = {n.path for n in graph.nodes if n.kind == "file" and n.path}
    resolved, _ = _resolve_file(file_paths, target)
    if resolved is None:
        return None

    view = GraphView(graph)
    node_id = file_id(resolved)

    direct = sorted(n.path for n in view.dependents(node_id) if n.path)
    affected = sorted(
        path
        for nid in view.transitive_dependents(node_id)
        if (path := _path_of(view, nid)) is not None
    )
    dependencies = sorted(n.path for n in view.dependencies(node_id) if n.path)
    affected_modules = sorted({_module_of(p) for p in affected})
    language = view.nodes[node_id].language if node_id in view.nodes else None

    risk_level, risks = _assess(len(affected), len(affected_modules), len(direct))

    return ImpactReport(
        target=target,
        file=resolved,
        language=language,
        direct_dependents=direct,
        affected_files=affected,
        affected_file_count=len(affected),
        affected_modules=affected_modules,
        dependencies=dependencies,
        risk_level=risk_level,
        risks=risks,
    )


def candidate_files(graph: ArchitectureGraph, target: str) -> list[str]:
    """Files that ambiguously match ``target`` (for 'did you mean' diagnostics)."""
    file_paths = {n.path for n in graph.nodes if n.kind == "file" and n.path}
    _, candidates = _resolve_file(file_paths, target)
    return candidates


def _resolve_file(file_paths: set[str], query: str) -> tuple[str | None, list[str]]:
    """Resolve a file by exact path, unique path suffix, or basename.

    Returns ``(path, [])`` on a unique match, ``(None, candidates)`` when the
    query is ambiguous, and ``(None, [])`` when nothing matches.
    """
    if query in file_paths:
        return query, []
    suffix = [p for p in file_paths if p.endswith(f"/{query}")]
    basename = [p for p in file_paths if p.rsplit("/", 1)[-1] == query]
    candidates = sorted(set(suffix) | set(basename))
    if len(candidates) == 1:
        return candidates[0], []
    return None, candidates


def _path_of(view: GraphView, node_id: str) -> str | None:
    node = view.nodes.get(node_id)
    return node.path if node else None


def _module_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


def _assess(affected: int, modules: int, direct: int) -> tuple[str, list[str]]:
    risks: list[str] = []
    if affected == 0:
        risks.append("No files import this — the change is isolated to the file itself.")
    else:
        risks.append(
            f"{affected} file(s) across {modules} module(s) transitively import this file."
        )
        if direct:
            risks.append(f"{direct} file(s) import it directly.")

    if affected >= _HIGH_FILES or modules >= _HIGH_MODULES:
        level = "high"
    elif affected >= _MEDIUM_FILES or modules >= _MEDIUM_MODULES:
        level = "medium"
    else:
        level = "low"
    return level, risks


__all__ = ["candidate_files", "compute_impact"]
