"""Intermediate representation produced by language parsers.

Parsers turn source text into these plain dataclasses; the builder turns them
into graph nodes and edges. Import targets are already resolved to repo-relative
paths by the parser (it owns the language's import semantics); class base/
interface names and call names stay as raw strings for the builder to resolve
against the global node indices.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedFunction:
    name: str
    line: int
    calls: list[str] = field(default_factory=list)


@dataclass
class ParsedClass:
    name: str
    line: int
    bases: list[str] = field(default_factory=list)  # -> "extends" edges
    interfaces: list[str] = field(default_factory=list)  # -> "implements" edges
    methods: list[ParsedFunction] = field(default_factory=list)


@dataclass
class ParsedFile:
    path: str
    language: str
    imports: list[str] = field(default_factory=list)  # resolved repo-relative paths
    classes: list[ParsedClass] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)  # top-level only
