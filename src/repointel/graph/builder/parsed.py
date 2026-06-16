"""Intermediate representation produced by language parsers.

Parsers turn source text into these models; the builder turns them into graph
nodes and edges. Import targets are already resolved to repo-relative paths by
the parser (it owns the language's import semantics); class base/interface names
and call names stay as raw strings for the builder to resolve against the global
node indices.

These are Pydantic models (not plain dataclasses) so the incremental cache
(Phase 7) can serialize parsed files to ``.repointel/cache.json`` and reuse them
for files that have not changed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedFunction(BaseModel):
    name: str
    line: int
    calls: list[str] = Field(default_factory=list)


class ParsedClass(BaseModel):
    name: str
    line: int
    bases: list[str] = Field(default_factory=list)  # -> "extends" edges
    interfaces: list[str] = Field(default_factory=list)  # -> "implements" edges
    methods: list[ParsedFunction] = Field(default_factory=list)


class ParsedFile(BaseModel):
    path: str
    language: str
    imports: list[str] = Field(default_factory=list)  # resolved repo-relative paths
    classes: list[ParsedClass] = Field(default_factory=list)
    functions: list[ParsedFunction] = Field(default_factory=list)  # top-level only
