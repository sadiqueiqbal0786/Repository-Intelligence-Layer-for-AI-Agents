"""JSON-backed repository memory under ``.repointel/`` (Phase 4 foundation).

Phase 2 writes ``repository.json`` here. Later phases add ``graph.json``,
``architecture.json``, ``modules.json``, and ``conventions.json`` alongside it.
"""

from __future__ import annotations

from pathlib import Path

from repointel.graph.builder.cache import BuildCache
from repointel.models import (
    ArchitectureGraph,
    ArchitectureSummary,
    Conventions,
    Knowledge,
    ModulesDoc,
    RepositoryInventory,
    RepoSummary,
)

REPOINTEL_DIRNAME = ".repointel"
REPOSITORY_FILENAME = "repository.json"
GRAPH_FILENAME = "graph.json"
REPO_SUMMARY_FILENAME = "repo.json"
ARCHITECTURE_FILENAME = "architecture.json"
MODULES_FILENAME = "modules.json"
CONVENTIONS_FILENAME = "conventions.json"
KNOWLEDGE_FILENAME = "knowledge.json"
CACHE_FILENAME = "cache.json"


def memory_dir(root: Path) -> Path:
    """The ``.repointel/`` directory for ``root``."""
    return Path(root) / REPOINTEL_DIRNAME


def repository_path(root: Path) -> Path:
    """Path to ``.repointel/repository.json`` for ``root``."""
    return memory_dir(root) / REPOSITORY_FILENAME


def graph_path(root: Path) -> Path:
    """Path to ``.repointel/graph.json`` for ``root``."""
    return memory_dir(root) / GRAPH_FILENAME


def write_repository(inventory: RepositoryInventory, root: Path) -> Path:
    """Persist an inventory to ``.repointel/repository.json`` and return its path."""
    return _write(inventory.model_dump_json(indent=2), memory_dir(root) / REPOSITORY_FILENAME)


def read_repository(root: Path) -> RepositoryInventory | None:
    """Load a previously written inventory, or ``None`` if absent."""
    path = repository_path(root)
    if not path.exists():
        return None
    return RepositoryInventory.model_validate_json(path.read_text(encoding="utf-8"))


def write_graph(graph: ArchitectureGraph, root: Path) -> Path:
    """Persist a graph to ``.repointel/graph.json`` and return its path."""
    return _write(graph.model_dump_json(indent=2), memory_dir(root) / GRAPH_FILENAME)


def read_graph(root: Path) -> ArchitectureGraph | None:
    """Load a previously written graph, or ``None`` if absent."""
    path = graph_path(root)
    if not path.exists():
        return None
    return ArchitectureGraph.model_validate_json(path.read_text(encoding="utf-8"))


def write_repo_summary(summary: RepoSummary, root: Path) -> Path:
    return _write(summary.model_dump_json(indent=2), memory_dir(root) / REPO_SUMMARY_FILENAME)


def read_repo_summary(root: Path) -> RepoSummary | None:
    return _read(memory_dir(root) / REPO_SUMMARY_FILENAME, RepoSummary)


def write_architecture(summary: ArchitectureSummary, root: Path) -> Path:
    return _write(summary.model_dump_json(indent=2), memory_dir(root) / ARCHITECTURE_FILENAME)


def read_architecture(root: Path) -> ArchitectureSummary | None:
    return _read(memory_dir(root) / ARCHITECTURE_FILENAME, ArchitectureSummary)


def write_modules(doc: ModulesDoc, root: Path) -> Path:
    return _write(doc.model_dump_json(indent=2), memory_dir(root) / MODULES_FILENAME)


def read_modules(root: Path) -> ModulesDoc | None:
    return _read(memory_dir(root) / MODULES_FILENAME, ModulesDoc)


def write_conventions(conventions: Conventions, root: Path) -> Path:
    return _write(conventions.model_dump_json(indent=2), memory_dir(root) / CONVENTIONS_FILENAME)


def read_conventions(root: Path) -> Conventions | None:
    return _read(memory_dir(root) / CONVENTIONS_FILENAME, Conventions)


def write_knowledge(knowledge: Knowledge, root: Path) -> Path:
    """Persist the knowledge layer to ``.repointel/knowledge.json``."""
    return _write(knowledge.model_dump_json(indent=2), memory_dir(root) / KNOWLEDGE_FILENAME)


def read_knowledge(root: Path) -> Knowledge | None:
    """Load the knowledge layer, or ``None`` if absent."""
    return _read(memory_dir(root) / KNOWLEDGE_FILENAME, Knowledge)


def write_cache(cache: BuildCache, root: Path) -> Path:
    """Persist the incremental build cache to ``.repointel/cache.json``."""
    return _write(cache.model_dump_json(indent=2), memory_dir(root) / CACHE_FILENAME)


def read_cache(root: Path) -> BuildCache | None:
    """Load the incremental build cache, or ``None`` if absent/unreadable."""
    path = memory_dir(root) / CACHE_FILENAME
    if not path.exists():
        return None
    try:
        return BuildCache.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None  # corrupt/old cache -> treat as absent (forces a full rebuild)


def _write(payload: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


def _read(path: Path, model: type):
    if not path.exists():
        return None
    return model.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = [
    "ARCHITECTURE_FILENAME",
    "CACHE_FILENAME",
    "CONVENTIONS_FILENAME",
    "GRAPH_FILENAME",
    "KNOWLEDGE_FILENAME",
    "MODULES_FILENAME",
    "REPOINTEL_DIRNAME",
    "REPOSITORY_FILENAME",
    "REPO_SUMMARY_FILENAME",
    "graph_path",
    "memory_dir",
    "read_architecture",
    "read_cache",
    "read_conventions",
    "read_graph",
    "read_knowledge",
    "read_modules",
    "read_repo_summary",
    "read_repository",
    "repository_path",
    "write_architecture",
    "write_cache",
    "write_conventions",
    "write_graph",
    "write_knowledge",
    "write_modules",
    "write_repo_summary",
    "write_repository",
]
