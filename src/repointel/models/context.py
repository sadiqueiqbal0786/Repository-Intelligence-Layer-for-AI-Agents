"""Platform entities (Phase 12).

:class:`ContextPack` is the payoff of the whole pipeline — the smallest
representation that still lets an agent *understand* a repository, assembled from
the derived memory so it can be loaded in one shot for a few thousand tokens.
:class:`BenchmarkResult` quantifies that win: raw source tokens vs. pack tokens.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextPack(BaseModel):
    """A compact, agent-loadable understanding of a repository."""

    name: str
    language: str | None = None
    framework: str | None = None
    architecture: str | None = None
    package_manager: str | None = None
    file_count: int = 0
    module_count: int = 0
    total_loc: int = 0
    dependency_count: int = 0
    entry_points: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    class_naming: str | None = None
    function_naming: str | None = None
    dependency_injection: str | None = None
    patterns: list[str] = Field(default_factory=list)
    testing: str | None = None
    top_dependencies: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    history: str | None = None
    confidence: str | None = None  # graph-coverage self-grade: high|medium|low
    warnings: list[str] = Field(default_factory=list)  # fail-loud trust caveats
    stale: bool = False  # memory drifted from the working tree (live check)


class BenchmarkResult(BaseModel):
    """Token-savings metrics for representing a repo as a context pack."""

    repo: str
    source_files: int = 0
    source_loc: int = 0
    source_bytes: int = 0
    raw_tokens_est: int = 0
    pack_tokens_est: int = 0
    compression_ratio: float = 0.0
    tokens_saved_est: int = 0
    analyze_seconds: float = 0.0
