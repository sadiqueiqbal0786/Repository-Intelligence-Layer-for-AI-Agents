"""Symbol lookup (definitions + references) over the architecture graph.

The single most common token-burn for an agent is "where is ``X`` defined / who
calls it?" — which otherwise means a grep plus reading whole files. The graph
already holds every class/function as a node with its ``path`` and ``line`` and
the ``calls``/``extends``/``implements`` edges between them, so that question is
one lookup here instead of a file crawl.

Reference edges are as accurate as the parsers that produced them (calls are
linked only for unambiguous single-definition names), so ``reference_count`` is a
floor, not a census — surfaced plainly rather than overstated.
"""

from __future__ import annotations

from repointel.graph.traversal import GraphView
from repointel.models import ArchitectureGraph, GraphNode

_REFERENCE_KINDS = ("calls", "extends", "implements")
_REFERENCE_LIMIT = 25


def find_symbol(graph: ArchitectureGraph, query: str) -> list[dict]:
    """Definitions matching ``query`` (a class/function name or ``Class.method``).

    Each result carries where it is defined and who references it, most-
    referenced first.
    """
    view = GraphView(graph)
    matches = [n for n in graph.nodes if _matches(n, query)]
    results = [_describe(view, node) for node in matches]
    results.sort(key=lambda r: (-r["reference_count"], r["path"], r["line"] or 0))
    return results


def _matches(node: GraphNode, query: str) -> bool:
    if node.kind not in ("class", "function"):
        return False
    if node.name == query:
        return True
    # Methods are stored as "Class.method"; match the bare member name too.
    return node.kind == "function" and node.name.rsplit(".", 1)[-1] == query


def _describe(view: GraphView, node: GraphNode) -> dict:
    referrers: list[dict] = []
    for edge in view._in.get(node.id, []):  # noqa: SLF001 - trusted internal index
        if edge.kind not in _REFERENCE_KINDS:
            continue
        caller = view.nodes.get(edge.source)
        if caller is not None:
            referrers.append(
                {
                    "name": caller.name,
                    "path": caller.path,
                    "line": caller.line,
                    "via": edge.kind,
                }
            )
    referrers.sort(key=lambda r: (r["path"] or "", r["line"] or 0))
    return {
        "name": node.name,
        "kind": node.kind,
        "path": node.path,
        "line": node.line,
        "language": node.language,
        "module": _parent_dir(node.path) if node.path else None,
        "reference_count": len(referrers),
        "referenced_by": referrers[:_REFERENCE_LIMIT],
    }


def _parent_dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


__all__ = ["find_symbol"]
