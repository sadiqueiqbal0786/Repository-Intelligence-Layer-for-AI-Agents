"""Example community plugin: Go language support for RepoIntel (Phase 10).

This is a *complete, working* third-party plugin that lives entirely outside the
RepoIntel core. It adds a Go source parser — extracting top-level ``func`` and
``type ... struct`` declarations into the graph IR — without editing a single
core file. Go's ``.go`` extension is already recognized by the core language
table, so a parser is all that's needed.

Install this package alongside RepoIntel (see ``pyproject.toml``) and the
``repointel.plugins`` entry point makes it discoverable automatically; or, in a
script, ``from repointel.plugins import register_plugin; register_plugin(go_plugin)``.
"""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder.parsed import ParsedClass, ParsedFile, ParsedFunction
from repointel.plugins import Plugin

_FUNC_RE = re.compile(r"(?m)^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(")
_TYPE_STRUCT_RE = re.compile(r"(?m)^type\s+([A-Za-z_]\w*)\s+struct\b")


class GoParser:
    """Parses Go source into the RepoIntel graph IR."""

    language = "Go"  # must match the core language name for ``.go`` files

    def make_resolver(self, files: set[str], root: Path) -> set[str]:
        # Go import resolution (package path -> repo file) is out of scope for
        # this example, so the resolver is just the known file set.
        return files

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        pf = ParsedFile(path=path, language=self.language)
        for match in _TYPE_STRUCT_RE.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            pf.classes.append(ParsedClass(name=match.group(1), line=line))
        for match in _FUNC_RE.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            pf.functions.append(ParsedFunction(name=match.group(1), line=line))
        return pf


# A parser-only plugin: Go's ecosystem scanner could be added later as `scanner=`.
go_plugin = Plugin(name="go", parser=GoParser())

__all__ = ["GoParser", "go_plugin"]
