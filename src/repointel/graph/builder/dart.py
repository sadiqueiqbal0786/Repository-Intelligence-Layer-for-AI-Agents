"""Dart source parsing via regular expressions.

Dart has no standard-library parser available from Python, so we extract the
high-signal, low-ambiguity constructs: import/export directives and class
headers (``extends`` / ``implements`` / ``with``). Top-level functions are
intentionally skipped — regex extraction of them is too noisy to hit the
accuracy bar.
"""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder.parsed import ParsedClass, ParsedFile

_IMPORT_RE = re.compile(r"""\bimport\s+['"]([^'"]+)['"]""")
# Barrel files re-export other files (`export 'goal_model.dart';`). An export is
# a real dependency edge — the barrel depends on what it re-exports — so
# resolving it lets a consumer that imports the barrel reach the underlying
# symbols transitively. Without this, changing a file that's only ever imported
# via a barrel looks safe when it isn't.
_EXPORT_RE = re.compile(r"""\bexport\s+['"]([^'"]+)['"]""")
_PACKAGE_NAME_RE = re.compile(r"(?m)^name:\s*(\S+)")


# Dirs that never hold a real Dart package and are expensive to walk. Local so
# this module keeps no dependency on the scanners package.
_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git", "node_modules", "build", "dist", ".venv", "venv", "__pycache__",
        ".dart_tool", ".pub-cache", "Pods", ".symlinks", "ephemeral", ".fvm",
        ".repointel", ".gradle", "vendor",
    }
)


def dart_packages(root: Path) -> dict[str, str]:
    """Map each Dart package ``name:`` → its ``lib/`` prefix (repo-relative,
    posix), by finding EVERY ``pubspec.yaml`` — not just one at the root.

    A Flutter app frequently lives in a subfolder (``app/pubspec.yaml``), so
    assuming the manifest sits at the repo root left every ``package:app/…``
    import unresolved and silently collapsed the whole import graph. Now
    ``package:<pkg>/<sub>`` resolves against the lib/ dir of whichever pubspec
    declares ``<pkg>`` (e.g. ``app/lib/<sub>``). Also handles monorepos.
    """
    packages: dict[str, str] = {}
    root = Path(root)
    for pubspec in root.rglob("pubspec.yaml"):
        if any(part in _IGNORED_DIRS for part in pubspec.parts):
            continue
        try:
            text = pubspec.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = _PACKAGE_NAME_RE.search(text)
        if not match:
            continue
        rel_dir = pubspec.parent.relative_to(root).as_posix()
        packages[match.group(1)] = "lib" if rel_dir in ("", ".") else f"{rel_dir}/lib"
    return packages


def dart_package_name(root: Path) -> str | None:
    """Back-compat: the name of any one declared package, or None."""
    return next(iter(dart_packages(root)), None)


_CLASS_RE = re.compile(r"\b(?:abstract\s+)?class\s+(\w+)([^{]*)\{", re.MULTILINE)
_GENERICS_RE = re.compile(r"<[^<>]*>")
_NAME_RE = re.compile(r"[\w$.]+")


class DartImportResolver:
    """Resolves Dart imports to repo-relative file paths."""

    def __init__(self, files: set[str], packages: dict[str, str] | str | None) -> None:
        self.files = files
        # Accept the new {name: lib_prefix} map; tolerate the old single-name
        # form (→ prefix "lib") so existing callers/tests keep working.
        if isinstance(packages, str):
            self.packages: dict[str, str] = {packages: "lib"}
        else:
            self.packages = packages or {}

    def resolve(self, spec: str, current_path: str) -> str | None:
        if spec.startswith("dart:"):
            return None
        if spec.startswith("package:"):
            rest = spec[len("package:") :]
            if "/" not in rest:
                return None
            pkg, sub = rest.split("/", 1)
            lib_prefix = self.packages.get(pkg)
            if lib_prefix:
                candidate = f"{lib_prefix}/{sub}"
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

    # Imports AND exports both create a dependency edge on the referenced file.
    for pattern in (_IMPORT_RE, _EXPORT_RE):
        for match in pattern.finditer(source):
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
