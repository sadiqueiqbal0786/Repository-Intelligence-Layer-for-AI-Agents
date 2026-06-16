"""Knowledge-layer entities (Phase 11).

The knowledge layer is the repository's *long-term memory* — the understanding
that structure alone can't capture: the architecture decisions behind the code,
the patterns it follows, and how the project has evolved. Unlike the derived
artifacts (which are regenerated every build), recorded decisions **accumulate**:
a manually captured decision survives rebuilds.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

KNOWLEDGE_SCHEMA_VERSION = 1


class Decision(BaseModel):
    """An architecture decision — discovered from an ADR or recorded by hand."""

    id: str
    title: str
    status: str | None = None  # e.g. "accepted" | "proposed" | "superseded"
    date: str | None = None  # ISO date
    context: str | None = None
    rationale: str | None = None
    source: str = "manual"  # "manual" | "adr:<path>" | "inferred"


class Pattern(BaseModel):
    """A recurring practice the codebase follows, with the evidence for it."""

    name: str
    kind: str  # "architecture" | "convention" | "structural" | "dependency" | "testing"
    description: str
    evidence: str | None = None


class Contributor(BaseModel):
    name: str
    commits: int = 0


class ProjectHistory(BaseModel):
    """Project evolution, derived from git (empty when not a git repo)."""

    is_git: bool = False
    total_commits: int = 0
    first_commit_date: str | None = None
    last_commit_date: str | None = None
    contributor_count: int = 0
    top_contributors: list[Contributor] = Field(default_factory=list)
    recent_commits: list[str] = Field(default_factory=list, description="Recent commit subjects.")


class Knowledge(BaseModel):
    """``knowledge.json`` — the durable knowledge layer."""

    schema_version: int = KNOWLEDGE_SCHEMA_VERSION
    decisions: list[Decision] = Field(default_factory=list)
    patterns: list[Pattern] = Field(default_factory=list)
    history: ProjectHistory = Field(default_factory=ProjectHistory)
