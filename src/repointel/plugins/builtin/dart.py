"""Built-in Dart plugin (Phase 10)."""

from __future__ import annotations

from pathlib import Path

from repointel.graph.builder.dart import (
    DartImportResolver,
    dart_package_name,
    parse_dart_file,
)
from repointel.graph.builder.parsed import ParsedFile
from repointel.plugins.base import Plugin
from repointel.scanners.dart import DartScanner


class DartParser:
    language = "Dart"

    def make_resolver(self, files: set[str], root: Path) -> DartImportResolver:
        return DartImportResolver(files, dart_package_name(root))

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        assert isinstance(resolver, DartImportResolver)
        return parse_dart_file(path, source, resolver)


dart_plugin = Plugin(name="dart", scanner=DartScanner(), parser=DartParser())

__all__ = ["DartParser", "dart_plugin"]
