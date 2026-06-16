"""Repository-memory orchestration (Phase 4).

``build_memory`` runs the full pipeline (scan → graph → derive summaries) into a
:class:`MemoryBundle`; ``persist_memory`` writes the canonical ``.repointel/``
artifact set; ``load_memory`` reads the derived summaries back so an agent can
understand the repo without rescanning.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repointel.context.architecture import summarize_architecture
from repointel.context.conventions import detect_conventions
from repointel.context.summary import summarize_modules
from repointel.graph.builder import build_graph
from repointel.models import (
    ArchitectureGraph,
    ArchitectureSummary,
    Conventions,
    ModulesDoc,
    RepositoryInventory,
    RepositoryMemory,
    RepoSummary,
)
from repointel.scanners import scan_repo
from repointel.storage.json import (
    ARCHITECTURE_FILENAME,
    CONVENTIONS_FILENAME,
    GRAPH_FILENAME,
    MODULES_FILENAME,
    REPO_SUMMARY_FILENAME,
    REPOSITORY_FILENAME,
    read_architecture,
    read_conventions,
    read_modules,
    read_repo_summary,
    write_architecture,
    write_conventions,
    write_graph,
    write_modules,
    write_repo_summary,
    write_repository,
)

# Order is meaningful: repository.json and graph.json are the raw layers; the
# rest are derived. repo.json lists them all as its manifest.
_ARTIFACTS = [
    REPOSITORY_FILENAME,
    GRAPH_FILENAME,
    REPO_SUMMARY_FILENAME,
    ARCHITECTURE_FILENAME,
    MODULES_FILENAME,
    CONVENTIONS_FILENAME,
]


@dataclass
class MemoryBundle:
    """Everything produced by a build, before/after persistence."""

    inventory: RepositoryInventory
    graph: ArchitectureGraph
    repo: RepoSummary
    architecture: ArchitectureSummary
    modules: ModulesDoc
    conventions: Conventions


def build_memory(root: Path) -> MemoryBundle:
    """Run the full analysis pipeline and assemble the memory bundle."""
    root = Path(root)
    inventory = scan_repo(root)
    graph = build_graph(root, inventory)
    architecture = summarize_architecture(inventory, graph)
    modules = summarize_modules(inventory, graph)
    conventions = detect_conventions(inventory)
    repo = _summarize_repo(inventory, graph)
    return MemoryBundle(
        inventory=inventory,
        graph=graph,
        repo=repo,
        architecture=architecture,
        modules=modules,
        conventions=conventions,
    )


def persist_memory(bundle: MemoryBundle, root: Path) -> list[Path]:
    """Write the full ``.repointel/`` artifact set; return the written paths."""
    root = Path(root)
    return [
        write_repository(bundle.inventory, root),
        write_graph(bundle.graph, root),
        write_repo_summary(bundle.repo, root),
        write_architecture(bundle.architecture, root),
        write_modules(bundle.modules, root),
        write_conventions(bundle.conventions, root),
    ]


def load_memory(root: Path) -> RepositoryMemory | None:
    """Load the derived memory summaries, or ``None`` if not yet built."""
    repo = read_repo_summary(root)
    if repo is None:
        return None
    architecture = read_architecture(root) or ArchitectureSummary()
    modules = read_modules(root) or ModulesDoc(path=str(Path(root)))
    conventions = read_conventions(root) or Conventions()
    return RepositoryMemory(
        repo=repo, architecture=architecture, modules=modules, conventions=conventions
    )


def _summarize_repo(inventory: RepositoryInventory, graph: ArchitectureGraph) -> RepoSummary:
    return RepoSummary(
        path=inventory.path,
        name=Path(inventory.path).name,
        fingerprint=inventory.fingerprint,
        file_count=inventory.file_count,
        module_count=inventory.module_count,
        dependency_count=inventory.dependency_count,
        total_loc=inventory.total_loc,
        node_count=graph.node_count,
        edge_count=graph.edge_count,
        entry_points=list(inventory.entry_points),
        artifacts=list(_ARTIFACTS),
    )


__all__ = ["MemoryBundle", "build_memory", "load_memory", "persist_memory"]
