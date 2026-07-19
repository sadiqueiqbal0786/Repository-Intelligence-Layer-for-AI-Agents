"""Domain models — the machine-readable contract shared across all layers.

In clean-architecture terms these are the *entities*: they depend on nothing
else in the package, and every other layer (scanners, graph, context, mcp)
depends on them.
"""

from __future__ import annotations

from repointel.models.context import BenchmarkResult, ContextPack
from repointel.models.explanation import ModuleExplanation
from repointel.models.fingerprint import Fingerprint
from repointel.models.graph import ArchitectureGraph, GraphEdge, GraphNode
from repointel.models.impact import ImpactReport
from repointel.models.inventory import (
    Dependency,
    FileEntry,
    Module,
    RepositoryInventory,
)
from repointel.models.knowledge import (
    Contributor,
    Decision,
    DocBrief,
    Knowledge,
    Note,
    Pattern,
    ProjectHistory,
)
from repointel.models.memory import (
    SCHEMA_VERSION,
    ArchitectureSummary,
    Conventions,
    GraphCoverage,
    LanguageCoverage,
    LayerSummary,
    ModulesDoc,
    ModuleSummary,
    NamingConventions,
    RepositoryMemory,
    RepoSummary,
    TestingConvention,
)

__all__ = [
    "SCHEMA_VERSION",
    "ArchitectureGraph",
    "ArchitectureSummary",
    "BenchmarkResult",
    "ContextPack",
    "Contributor",
    "Conventions",
    "Decision",
    "Dependency",
    "DocBrief",
    "FileEntry",
    "Fingerprint",
    "GraphCoverage",
    "GraphEdge",
    "GraphNode",
    "LanguageCoverage",
    "ImpactReport",
    "Knowledge",
    "LayerSummary",
    "Module",
    "ModuleExplanation",
    "ModuleSummary",
    "ModulesDoc",
    "NamingConventions",
    "Note",
    "Pattern",
    "ProjectHistory",
    "RepoSummary",
    "RepositoryInventory",
    "RepositoryMemory",
    "TestingConvention",
]
