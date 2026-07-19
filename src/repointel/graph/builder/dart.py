"""Dart source parsing via regular expressions.

Dart has no standard-library parser available from Python, so we extract the
high-signal, low-ambiguity constructs: import/export directives, class headers
(``extends`` / ``implements`` / ``with``), and — conservatively — top-level
functions and class methods.

Function/method extraction is deliberately precision-first: it only accepts
declarations that carry an explicit return type (``Widget build(...)``,
``Future<void> load()``, ``String get name``), which is the overwhelmingly
common Flutter/Dart style and excludes bare calls and control-flow (``if (``,
``for (``) that have no type token. Constructors and untyped closures are
skipped rather than risk false positives. Comments and string literals are
blanked before matching so their contents never masquerade as code (this also
makes brace-matching for class bodies reliable).
"""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder.parsed import ParsedClass, ParsedFile, ParsedFunction

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

# A function/method declaration: an explicit return type, then the name, then a
# parameter list. Anchored to a statement/block boundary so it never fires on a
# call embedded in an expression. The return type is required — that is what
# separates a declaration from a bare call and keeps precision high.
_FUNCTION_RE = re.compile(
    r"""
    (?:^|[;{}])                              # statement / block boundary
    [ \t\r\n]*
    (?:@[\w$]+(?:\([^)]*\))?[ \t\r\n]*)*      # optional annotations
    (?:(?:static|final|const|external|abstract|late)[ \t]+)*
    (?P<type>[A-Za-z_$][\w$]*(?:<[^;{}]*?>)?(?:[ \t]*\?)?)  # return type (required)
    [ \t]+
    (?:get[ \t]+)?                            # getter form: `T get name`
    (?P<name>[A-Za-z_$][\w$]*)
    [ \t]*
    (?:<[^<>;{}]*>)?                          # optional generic type params
    [ \t]*\(                                  # start of the parameter list
    """,
    re.VERBOSE,
)

# A getter has no parameter list: `Type get name => ...` / `Type get name { ... }`.
# Handled separately so the shared declaration regex can keep requiring "(".
_GETTER_RE = re.compile(
    r"""
    (?:^|[;{}])
    [ \t\r\n]*
    (?:@[\w$]+(?:\([^)]*\))?[ \t\r\n]*)*
    (?:(?:static|final|const|external|abstract|late)[ \t]+)*
    (?P<type>[A-Za-z_$][\w$]*(?:<[^;{}]*?>)?(?:[ \t]*\?)?)
    [ \t]+get[ \t]+
    (?P<name>[A-Za-z_$][\w$]*)
    [ \t]*(?:=>|\{)
    """,
    re.VERBOSE,
)

# Words that can appear in the "type name(" shape but are not declarations. If
# either the return-type token or the name is one of these, it's control flow or
# a call (`return foo(`, `await bar(`, `} else if (`), not a function.
_DART_NON_DECL = frozenset(
    {
        "return", "await", "yield", "throw", "if", "else", "for", "while", "do",
        "switch", "case", "catch", "new", "assert", "rethrow", "break", "continue",
        "super", "this", "is", "as", "in", "with", "extends", "implements", "on",
        "try", "finally", "class", "enum", "typedef", "mixin", "extension", "part",
        "import", "export", "library", "show", "hide", "default",
        "Function",  # `void Function() cb` is a function-typed field, not a decl
        # Modifiers/keywords a regex could mistake for the return type via
        # backtracking (`const Widget(` -> type "const", name "Widget"). None is
        # ever a real return type, so rejecting them kills that whole class of
        # false positive (notably const constructors).
        "const", "final", "static", "var", "late", "external", "abstract",
        "factory", "covariant", "required",
    }
)


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
    # Directives are matched on the raw source; string blanking would erase the
    # quoted path they need.
    for pattern in (_IMPORT_RE, _EXPORT_RE):
        for match in pattern.finditer(source):
            if (target := resolver.resolve(match.group(1), path)) and target != path:
                pf.imports.append(target)
    pf.imports = sorted(set(pf.imports))

    # Everything below reads code structure, so work on a copy with comments and
    # string bodies blanked out — no keyword or brace hiding inside a literal.
    code = _blank_noise(source)

    classes: list[tuple[ParsedClass, int, int]] = []  # (class, body_start, body_end)
    for match in _CLASS_RE.finditer(code):
        name = match.group(1)
        header = _GENERICS_RE.sub("", match.group(2))
        line = code.count("\n", 0, match.start()) + 1
        body_start = match.end() - 1  # index of the opening brace
        body_end = _matching_brace(code, body_start)
        cls = ParsedClass(
            name=name,
            line=line,
            bases=_clause(header, "extends"),
            interfaces=_clause(header, "implements") + _clause(header, "with"),
        )
        classes.append((cls, body_start, body_end))
        pf.classes.append(cls)

    # Attribute each declaration to the innermost enclosing class (a method) or
    # to the file (a top-level function). Dedupe by (name, offset) so a getter
    # and a function never double-count the same site.
    seen: set[tuple[str, int]] = set()
    for pattern in (_FUNCTION_RE, _GETTER_RE):
        for match in pattern.finditer(code):
            type_token = match.group("type").split("<", 1)[0].strip("?").strip()
            name = match.group("name")
            if type_token in _DART_NON_DECL or name in _DART_NON_DECL:
                continue
            pos = match.start("name")
            if (name, pos) in seen:
                continue
            seen.add((name, pos))
            line = code.count("\n", 0, pos) + 1
            owner = _innermost_class(classes, pos)
            fn = ParsedFunction(name=name, line=line)
            if owner is None:
                pf.functions.append(fn)
            elif name != owner.name:  # skip constructors (name == class name)
                owner.methods.append(fn)
    return pf


def _blank_noise(source: str) -> str:
    """Return ``source`` with comment and string-literal bodies replaced by
    spaces (newlines preserved), so line numbers and offsets stay stable while
    code-structure regexes never match inside a comment or string."""
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        two = source[i : i + 2]
        if two == "//":
            j = source.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = source.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(_blank_keep_newlines(source[i:j]))
            i = j
        elif ch in "'\"":
            j, blanked = _consume_string(source, i)
            out.append(blanked)
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _consume_string(source: str, start: int) -> tuple[int, str]:
    """Consume a Dart string literal beginning at ``start``; return the index
    just past it and a same-length blank (keeping the quotes and newlines)."""
    n = len(source)
    raw = start > 0 and source[start - 1] == "r"
    quote = source[start]
    triple = source[start : start + 3] in ("'''", '"""')
    delim = quote * 3 if triple else quote
    i = start + len(delim)
    while i < n:
        if not raw and source[i] == "\\":
            i += 2
            continue
        if source[i : i + len(delim)] == delim:
            i += len(delim)
            break
        i += 1
    body = source[start:i]
    # Keep the opening/closing quotes so adjacency isn't broken; blank the middle.
    if len(body) >= 2 * len(delim):
        inner = _blank_keep_newlines(body[len(delim) : len(body) - len(delim)])
    else:
        inner = ""
    return i, delim + inner + delim


def _blank_keep_newlines(text: str) -> str:
    return "".join("\n" if c == "\n" else " " for c in text)


def _matching_brace(code: str, open_index: int) -> int:
    """Index just past the ``}`` matching the ``{`` at ``open_index`` (or end of
    string if unbalanced). ``code`` must already be noise-blanked."""
    depth = 0
    for i in range(open_index, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(code)


def _innermost_class(
    classes: list[tuple[ParsedClass, int, int]], pos: int
) -> ParsedClass | None:
    """The class whose body most tightly encloses ``pos`` (handles nested
    classes/extensions), or ``None`` when ``pos`` is top-level."""
    best: ParsedClass | None = None
    best_start = -1
    for cls, start, end in classes:
        if start < pos < end and start > best_start:
            best, best_start = cls, start
    return best


def _clause(header: str, keyword: str) -> list[str]:
    """Extract the comma-separated type names following ``keyword`` in a header."""
    match = re.search(rf"\b{keyword}\s+([^{{]*)", header)
    if not match:
        return []
    # Stop at the next clause keyword so "extends A implements B" doesn't bleed.
    segment = re.split(r"\b(?:extends|implements|with)\b", match.group(1))[0]
    return [m.group(0).split(".")[-1] for m in _NAME_RE.finditer(segment)]
