"""Inventory entities (Phase 2) — a complete, machine-readable census of a repo."""

from __future__ import annotations

from pydantic import BaseModel, Field

from repointel.models.fingerprint import Fingerprint


class FileEntry(BaseModel):
    """A single indexed file."""

    path: str  # repo-relative, posix-style
    language: str | None = None
    size: int = 0  # bytes
    loc: int = 0  # raw line count (code files only)


class Module(BaseModel):
    """A directory that directly contains source files."""

    path: str  # "." denotes the repository root
    language: str | None = None
    file_count: int = 0


class Dependency(BaseModel):
    """A declared third-party dependency."""

    name: str
    version: str | None = None
    source: str  # the manifest that declared it
    dev: bool = False


class RepositoryInventory(BaseModel):
    """The Phase 2 census, persisted to ``.repointel/repository.json``."""

    path: str
    fingerprint: Fingerprint
    files: list[FileEntry] = Field(default_factory=list)
    directories: list[str] = Field(default_factory=list)
    modules: list[Module] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    configs: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)

    # Headline counts (kept as fields so the JSON is self-describing for agents).
    file_count: int = 0
    directory_count: int = 0
    module_count: int = 0
    dependency_count: int = 0
    total_loc: int = 0
