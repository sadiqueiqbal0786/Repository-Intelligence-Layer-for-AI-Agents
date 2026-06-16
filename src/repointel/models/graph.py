"""Architecture-graph entities (Phase 3).

A directed graph of code elements. Nodes are files/modules/classes/functions;
edges are structural (``contains``) or semantic (``imports``/``extends``/
``implements``/``calls``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

NodeKind = str  # "module" | "file" | "class" | "function" | "service" | "route" | "database"
EdgeKind = str  # "contains" | "imports" | "extends" | "implements" | "calls" | "depends_on"


class GraphNode(BaseModel):
    id: str  # stable, unique (e.g. "class:src/demo/models.py:User")
    kind: NodeKind
    name: str
    path: str | None = None  # repo-relative file the element lives in
    line: int | None = None
    language: str | None = None


class GraphEdge(BaseModel):
    source: str  # node id
    target: str  # node id
    kind: EdgeKind


class ArchitectureGraph(BaseModel):
    """The Phase 3 graph, persisted to ``.repointel/graph.json``."""

    path: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    node_kinds: dict[str, int] = Field(default_factory=dict)
    edge_kinds: dict[str, int] = Field(default_factory=dict)
