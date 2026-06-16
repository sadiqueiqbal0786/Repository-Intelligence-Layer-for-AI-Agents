"""Explanation entities (Phase 8).

A :class:`ModuleExplanation` is a structured, LLM-free narrative about one
module, derived entirely from repository memory (graph + summaries). It answers
the questions a developer or agent asks before touching code: what is this, what
does it depend on, who depends on it, and how risky is it to change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModuleExplanation(BaseModel):
    target: str  # the query as asked
    module: str  # resolved module path
    language: str | None = None
    purpose: str = ""  # generated from structure + naming conventions
    file_count: int = 0
    class_count: int = 0
    function_count: int = 0
    loc: int = 0
    key_classes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(
        default_factory=list, description="Module paths this module imports."
    )
    consumers: list[str] = Field(
        default_factory=list, description="Module paths that import this module."
    )
    critical_files: list[str] = Field(
        default_factory=list, description="This module's most-depended-on files."
    )
    entry_points: list[str] = Field(default_factory=list)
    blast_radius: int = Field(
        default=0, description="Files that transitively depend on this module."
    )
    risk_level: str = "low"  # "low" | "medium" | "high"
    risks: list[str] = Field(default_factory=list)
