"""Graph traversal — query helpers over an :class:`ArchitectureGraph` (Phase 3).

Builds adjacency indices once, then answers the questions later phases need:
neighbors by edge kind, import dependencies/dependents, lookup by path or name.
Phase 9 (impact analysis) builds on this.
"""

from __future__ import annotations

from collections import defaultdict, deque

from repointel.models import ArchitectureGraph, GraphEdge, GraphNode


class GraphView:
    def __init__(self, graph: ArchitectureGraph) -> None:
        self.graph = graph
        self.nodes: dict[str, GraphNode] = {n.id: n for n in graph.nodes}
        self._out: dict[str, list[GraphEdge]] = defaultdict(list)
        self._in: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in graph.edges:
            self._out[edge.source].append(edge)
            self._in[edge.target].append(edge)

    def neighbors(
        self, node_id: str, *, kind: str | None = None, incoming: bool = False
    ) -> list[GraphNode]:
        """Adjacent nodes, optionally filtered to a single edge kind."""
        edges = self._in[node_id] if incoming else self._out[node_id]
        out: list[GraphNode] = []
        for edge in edges:
            if kind is not None and edge.kind != kind:
                continue
            other = edge.source if incoming else edge.target
            if other in self.nodes:
                out.append(self.nodes[other])
        return out

    def dependencies(self, node_id: str) -> list[GraphNode]:
        """Files imported by ``node_id`` (outgoing ``imports`` edges)."""
        return self.neighbors(node_id, kind="imports")

    def dependents(self, node_id: str) -> list[GraphNode]:
        """Files that import ``node_id`` (incoming ``imports`` edges)."""
        return self.neighbors(node_id, kind="imports", incoming=True)

    def nodes_for_path(self, path: str) -> list[GraphNode]:
        return [n for n in self.graph.nodes if n.path == path]

    def find(self, name: str, *, kind: str | None = None) -> list[GraphNode]:
        return [
            n for n in self.graph.nodes if n.name == name and (kind is None or n.kind == kind)
        ]

    def transitive_dependents(self, node_id: str) -> set[str]:
        """All nodes that reach ``node_id`` through ``imports`` edges (any depth)."""
        seen: set[str] = set()
        queue: deque[str] = deque([node_id])
        while queue:
            current = queue.popleft()
            for edge in self._in[current]:
                if edge.kind == "imports" and edge.source not in seen:
                    seen.add(edge.source)
                    queue.append(edge.source)
        return seen


__all__ = ["GraphView"]
