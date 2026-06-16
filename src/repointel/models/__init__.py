"""Domain models — the machine-readable contract shared across all layers.

In clean-architecture terms these are the *entities*: they depend on nothing
else in the package, and every other layer (scanners, graph, context, mcp)
depends on them.
"""

from __future__ import annotations

from repointel.models.fingerprint import Fingerprint
from repointel.models.graph import ArchitectureGraph, GraphEdge, GraphNode
from repointel.models.inventory import (
    Dependency,
    FileEntry,
    Module,
    RepositoryInventory,
)
from repointel.models.memory import (
    SCHEMA_VERSION,
    ArchitectureSummary,
    Conventions,
    LayerSummary,
    ModulesDoc,
    ModuleSummary,
    RepositoryMemory,
    RepoSummary,
    TestingConvention,
)

__all__ = [
    "SCHEMA_VERSION",
    "ArchitectureGraph",
    "ArchitectureSummary",
    "Conventions",
    "Dependency",
    "FileEntry",
    "Fingerprint",
    "GraphEdge",
    "GraphNode",
    "LayerSummary",
    "Module",
    "ModuleSummary",
    "ModulesDoc",
    "RepoSummary",
    "RepositoryInventory",
    "RepositoryMemory",
    "TestingConvention",
]
