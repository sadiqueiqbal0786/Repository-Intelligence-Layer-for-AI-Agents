"""Architecture-style detection.

Phase 1 ships a directory-name heuristic. Phase 6 (Convention Discovery) will
enrich this with dependency-direction analysis from the graph layer.
"""

from __future__ import annotations

from repointel.models import (
    ArchitectureGraph,
    ArchitectureSummary,
    Fingerprint,
    LayerSummary,
    RepositoryInventory,
)
from repointel.scanners.base import RepoContext

# Path segments stripped when grouping modules into logical layers.
_SOURCE_ROOTS = frozenset({"src", "lib", "app"})


def detect_architecture(ctx: RepoContext, fp: Fingerprint) -> None:
    """Infer an architectural style from source directory names.

    Order matters: most specific style wins.
    """
    dirs = ctx.source_dirs()
    segments = {seg.lower() for path in dirs for seg in path.split("/")}

    def has(*names: str) -> bool:
        return all(n in segments for n in names)

    # Clean architecture: domain + data/infrastructure + presentation/application layers.
    if has("domain", "data", "presentation") or has("domain", "application", "infrastructure"):
        fp.set("architecture", "Clean Architecture", "domain/data/presentation layers")
        return

    # Feature-based: a top-level features/ or modules/ directory.
    if "features" in segments or "modules" in segments:
        fp.set("architecture", "Feature Based", "features/ or modules/ directory")
        return

    # Classic layered (controller/service/repository).
    layered = sum(
        any(seg.startswith(p) for seg in segments)
        for p in ("controller", "service", "repositor")
    )
    if layered >= 2:
        fp.set("architecture", "Layered", "controller/service/repository directories")
        return

    # MVC.
    if has("models", "views", "controllers"):
        fp.set("architecture", "MVC", "models/views/controllers directories")
        return

    # Conventional src layout.
    if "src" in segments or "lib" in segments:
        fp.set("architecture", "Standard (src/lib layout)", "src/ or lib/ directory")


def summarize_architecture(
    inventory: RepositoryInventory, graph: ArchitectureGraph
) -> ArchitectureSummary:
    """Derive ``architecture.json`` from the inventory and graph (Phase 4)."""
    fp = inventory.fingerprint
    return ArchitectureSummary(
        style=fp.architecture,
        languages=dict(fp.languages),
        framework=fp.framework,
        state_management=fp.state_management,
        navigation=fp.navigation,
        databases=list(fp.databases),
        layers=_layers(inventory),
        key_files=_key_files(graph),
        module_count=inventory.module_count,
        node_count=graph.node_count,
        edge_count=graph.edge_count,
    )


def _layer_of(path: str) -> str:
    parts = path.split("/")
    if parts and parts[0] in _SOURCE_ROOTS:
        parts = parts[1:]
    return parts[0] if parts and parts[0] else "(root)"


def _layers(inventory: RepositoryInventory) -> list[LayerSummary]:
    grouped: dict[str, LayerSummary] = {}
    for module in inventory.modules:
        name = _layer_of(module.path)
        layer = grouped.setdefault(name, LayerSummary(name=name))
        layer.modules.append(module.path)
        layer.file_count += module.file_count
    for layer in grouped.values():
        layer.modules.sort()
    return sorted(grouped.values(), key=lambda layer: (-layer.file_count, layer.name))


def _key_files(graph: ArchitectureGraph, *, limit: int = 10) -> list[str]:
    """Files with the most incoming ``imports`` edges — the architectural hubs."""
    in_degree: dict[str, int] = {}
    for edge in graph.edges:
        if edge.kind == "imports":
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
    id_to_path = {n.id: n.path for n in graph.nodes if n.path}
    ranked = sorted(in_degree.items(), key=lambda kv: (-kv[1], kv[0]))
    paths = [id_to_path[node_id] for node_id, _ in ranked if node_id in id_to_path]
    return paths[:limit]
