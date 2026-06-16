"""The :class:`Fingerprint` entity — a high-level identity card for a repo."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Fingerprint(BaseModel):
    """A high-level identity card for a repository (Phase 1).

    Every field is optional because real repositories are messy. Scanners fill
    in what they can prove and record *why* in :attr:`evidence`.
    """

    path: str
    language: str | None = Field(
        default=None, description="Primary programming language by source file count."
    )
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Detected code languages mapped to their source file counts.",
    )
    framework: str | None = None
    package_manager: str | None = None
    build_system: str | None = None
    state_management: str | None = None
    navigation: str | None = None
    databases: list[str] = Field(default_factory=list)
    architecture: str | None = None
    evidence: dict[str, str] = Field(
        default_factory=dict,
        description="Maps a detected attribute to the marker/file that proved it.",
    )

    def set(self, attr: str, value: str, evidence: str) -> None:
        """Set an attribute and record the evidence that produced it."""
        setattr(self, attr, value)
        self.evidence[attr] = evidence
