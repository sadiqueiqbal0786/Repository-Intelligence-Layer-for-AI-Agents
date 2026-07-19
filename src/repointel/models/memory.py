"""Repository-memory entities (Phase 4).

These are the derived, agent-consumable artifacts written under ``.repointel/``:
``repo.json`` (overview), ``architecture.json``, ``modules.json``, and
``conventions.json``. Together with ``repository.json`` (inventory) and
``graph.json`` (graph) they form the repository's permanent memory layer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from repointel.models.fingerprint import Fingerprint

SCHEMA_VERSION = 1


class LayerSummary(BaseModel):
    """A logical layer (top-level grouping of modules)."""

    name: str
    modules: list[str] = Field(default_factory=list)
    file_count: int = 0


class ArchitectureSummary(BaseModel):
    """``architecture.json`` — the shape of the system at a glance."""

    style: str | None = None
    languages: dict[str, int] = Field(default_factory=dict)
    framework: str | None = None
    state_management: str | None = None
    navigation: str | None = None
    databases: list[str] = Field(default_factory=list)
    layers: list[LayerSummary] = Field(default_factory=list)
    key_files: list[str] = Field(
        default_factory=list, description="Most-imported files (highest in-degree)."
    )
    module_count: int = 0
    node_count: int = 0
    edge_count: int = 0


class ModuleSummary(BaseModel):
    path: str
    language: str | None = None
    file_count: int = 0
    loc: int = 0
    classes: int = 0
    functions: int = 0
    files: list[str] = Field(default_factory=list)
    imports: list[str] = Field(
        default_factory=list, description="Other module paths this module imports."
    )


class ModulesDoc(BaseModel):
    """``modules.json`` — per-module breakdown."""

    path: str
    modules: list[ModuleSummary] = Field(default_factory=list)


class TestingConvention(BaseModel):
    framework: str | None = None
    test_dir: str | None = None
    test_count: int = 0


class NamingConventions(BaseModel):
    """Dominant identifier-casing styles, inferred from the graph.

    Each value is a casing label (e.g. ``"snake_case"``, ``"PascalCase"``,
    ``"camelCase"``), ``"mixed"`` when no style holds a clear majority, or
    ``None`` when there was nothing to measure.

    ``classes``/``functions`` report the **primary language's** convention (so a
    Dart project reads ``camelCase`` functions, not a language-agnostic
    ``snake_case``). ``*_by_language`` carry the full per-language breakdown for
    polyglot repos.
    """

    files: str | None = None
    classes: str | None = None
    functions: str | None = None
    classes_by_language: dict[str, str] = Field(default_factory=dict)
    functions_by_language: dict[str, str] = Field(default_factory=dict)


class Conventions(BaseModel):
    """``conventions.json`` — how the team writes code (deepened in Phase 6)."""

    architecture: str | None = None
    source_layout: str | None = None  # "src" | "lib" | "flat"
    package_manager: str | None = None
    build_system: str | None = None
    file_naming: str | None = None  # "snake_case" | "kebab-case" | "camelCase" | "mixed"
    naming: NamingConventions = Field(default_factory=NamingConventions)
    dependency_injection: str | None = Field(
        default=None, description="Detected DI/wiring framework (e.g. FastAPI, Riverpod, Spring)."
    )
    layering: list[str] = Field(
        default_factory=list,
        description="Recurring layer directory names that reveal the decomposition.",
    )
    patterns: list[str] = Field(
        default_factory=list,
        description="Detected structural patterns (e.g. repository_pattern, service_layer).",
    )
    testing: TestingConvention = Field(default_factory=TestingConvention)


class LanguageCoverage(BaseModel):
    """How completely one language is understood in the memory."""

    language: str
    files: int = 0
    graphed: bool = False  # False => inventory only, no dependency graph


class GraphCoverage(BaseModel):
    """``coverage.json`` — a fail-loud self-assessment of how much of the repo
    the graph actually resolved, so an agent knows how far to trust it.

    ``connectivity`` is the fraction of graphed source files that have at least
    one import edge; a value near zero on a real app is the tell-tale of
    unresolved imports (e.g. a package manifest that wasn't found), the exact
    failure mode that otherwise ships silently.
    """

    confidence: str = "unknown"  # "high" | "medium" | "low" | "unknown"
    source_files: int = 0  # files in a graphed language
    connected_files: int = 0  # of those, ones with >=1 import edge
    isolated_files: int = 0  # of those, ones with no import edge
    connectivity: float = 0.0  # connected_files / source_files (0..1)
    import_edges: int = 0
    languages: list[LanguageCoverage] = Field(default_factory=list)
    ungraphed_languages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RepoSummary(BaseModel):
    """``repo.json`` — the small, loadable overview / manifest."""

    schema_version: int = SCHEMA_VERSION
    path: str
    name: str
    fingerprint: Fingerprint
    file_count: int = 0
    module_count: int = 0
    dependency_count: int = 0
    total_loc: int = 0
    node_count: int = 0
    edge_count: int = 0
    entry_points: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    coverage: GraphCoverage | None = None


class RepositoryMemory(BaseModel):
    """In-memory bundle of every artifact, returned by the memory loader."""

    repo: RepoSummary
    architecture: ArchitectureSummary
    modules: ModulesDoc
    conventions: Conventions
