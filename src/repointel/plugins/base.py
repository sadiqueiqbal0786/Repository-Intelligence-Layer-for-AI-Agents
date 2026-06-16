"""Plugin interfaces (Phase 10).

A :class:`LanguagePlugin` bundles a repository's two per-language extension
points behind one object:

- a :class:`~repointel.scanners.base.Scanner` — ecosystem detection
  (fingerprint, dependencies, entry points), and
- a :class:`Parser` — source text → the :class:`ParsedFile` IR the graph builder
  turns into nodes and edges.

Either may be ``None``: a scanner-only plugin recognizes an ecosystem without
graphing it; a parser-only plugin graphs a language whose ecosystem is already
covered. Community languages ship as plugins discovered at runtime (see
:mod:`repointel.plugins.registry`) — no core file is edited to add one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from repointel.graph.builder.parsed import ParsedFile
from repointel.scanners.base import Scanner


@runtime_checkable
class Parser(Protocol):
    """Parses one language's source into the graph IR."""

    language: str  # canonical language name, matching ``CODE_EXTENSIONS`` (e.g. "Python")

    def make_resolver(self, files: set[str], root: Path) -> object:
        """Build an import resolver for this build (the parser owns its type)."""
        ...

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        """Parse one file; return ``None`` if it can't be parsed."""
        ...


@runtime_checkable
class LanguagePlugin(Protocol):
    name: str
    scanner: Scanner | None
    parser: Parser | None


@dataclass(frozen=True)
class Plugin:
    """A concrete :class:`LanguagePlugin` — what built-in and most third-party
    plugins instantiate."""

    name: str
    scanner: Scanner | None = None
    parser: Parser | None = None


__all__ = ["LanguagePlugin", "Parser", "Plugin"]
