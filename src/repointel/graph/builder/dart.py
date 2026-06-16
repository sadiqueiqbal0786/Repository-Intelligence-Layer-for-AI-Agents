"""Dart source parsing via regular expressions.

Dart has no standard-library parser available from Python, so we extract the
high-signal, low-ambiguity constructs: import directives and class headers
(``extends`` / ``implements`` / ``with``). Top-level functions are intentionally
skipped — regex extraction of them is too noisy to hit the accuracy bar.
"""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder.parsed import ParsedClass, ParsedFile

_IMPORT_RE = re.compile(r"""\bimport\s+['"]([^'"]+)['"]""")
_PACKAGE_NAME_RE = re.compile(r"(?m)^name:\s*(\S+)")


def dart_package_name(root: Path) -> str | None:
    """Read the package ``name:`` from ``pubspec.yaml`` (used to resolve
    ``package:`` imports back to ``lib/`` paths)."""
    try:
        text = (Path(root) / "pubspec.yaml").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = _PACKAGE_NAME_RE.search(text)
    return match.group(1) if match else None
_CLASS_RE = re.compile(r"\b(?:abstract\s+)?class\s+(\w+)([^{]*)\{", re.MULTILINE)
_GENERICS_RE = re.compile(r"<[^<>]*>")
_NAME_RE = re.compile(r"[\w$.]+")


class DartImportResolver:
    """Resolves Dart imports to repo-relative file paths."""

    def __init__(self, files: set[str], package_name: str | None) -> None:
        self.files = files
        self.package_name = package_name

    def resolve(self, spec: str, current_path: str) -> str | None:
        if spec.startswith("dart:"):
            return None
        if spec.startswith("package:"):
            rest = spec[len("package:") :]
            if "/" not in rest:
                return None
            pkg, sub = rest.split("/", 1)
            if self.package_name and pkg == self.package_name:
                candidate = f"lib/{sub}"
                return candidate if candidate in self.files else None
            return None

        # Relative import resolved against the current file's directory.
        parts = current_path.split("/")[:-1]
        for segment in spec.split("/"):
            if segment in ("", "."):
                continue
            if segment == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(segment)
        candidate = "/".join(parts)
        return candidate if candidate in self.files else None


def parse_dart_file(path: str, source: str, resolver: DartImportResolver) -> ParsedFile | None:
    pf = ParsedFile(path=path, language="Dart")

    for match in _IMPORT_RE.finditer(source):
        if (target := resolver.resolve(match.group(1), path)) and target != path:
            pf.imports.append(target)
    pf.imports = sorted(set(pf.imports))

    for match in _CLASS_RE.finditer(source):
        name = match.group(1)
        header = _GENERICS_RE.sub("", match.group(2))
        line = source.count("\n", 0, match.start()) + 1
        pf.classes.append(
            ParsedClass(
                name=name,
                line=line,
                bases=_clause(header, "extends"),
                interfaces=_clause(header, "implements") + _clause(header, "with"),
            )
        )
    return pf


def _clause(header: str, keyword: str) -> list[str]:
    """Extract the comma-separated type names following ``keyword`` in a header."""
    match = re.search(rf"\b{keyword}\s+([^{{]*)", header)
    if not match:
        return []
    # Stop at the next clause keyword so "extends A implements B" doesn't bleed.
    segment = re.split(r"\b(?:extends|implements|with)\b", match.group(1))[0]
    return [m.group(0).split(".")[-1] for m in _NAME_RE.finditer(segment)]
