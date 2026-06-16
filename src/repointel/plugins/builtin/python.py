"""Built-in Python plugin (Phase 10)."""

from __future__ import annotations

from pathlib import Path

from repointel.graph.builder.parsed import ParsedFile
from repointel.graph.builder.python import PyImportResolver, parse_python_file
from repointel.plugins.base import Plugin
from repointel.scanners.python import PythonScanner


class PythonParser:
    language = "Python"

    def make_resolver(self, files: set[str], root: Path) -> PyImportResolver:
        return PyImportResolver(files)

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        assert isinstance(resolver, PyImportResolver)
        return parse_python_file(path, source, resolver)


python_plugin = Plugin(name="python", scanner=PythonScanner(), parser=PythonParser())

__all__ = ["PythonParser", "python_plugin"]
