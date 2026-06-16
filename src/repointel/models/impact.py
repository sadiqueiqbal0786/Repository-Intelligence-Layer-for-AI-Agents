"""Change-impact entities (Phase 9).

An :class:`ImpactReport` predicts the consequences of changing one file: which
files transitively import it (the blast radius), which modules those span, what
the file itself depends on, and a derived risk level — all from the graph, no
LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImpactReport(BaseModel):
    target: str  # the query as asked
    file: str  # resolved repo-relative path
    language: str | None = None
    direct_dependents: list[str] = Field(
        default_factory=list, description="Files that import this file directly."
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="Files that transitively import this file — the blast radius.",
    )
    affected_file_count: int = 0
    affected_modules: list[str] = Field(
        default_factory=list, description="Modules containing the affected files."
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Files this file imports (its own upstream)."
    )
    risk_level: str = "low"  # "low" | "medium" | "high"
    risks: list[str] = Field(default_factory=list)
