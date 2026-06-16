"""Python source parsing via the standard-library ``ast`` module."""

from __future__ import annotations

import ast

from repointel.graph.builder.parsed import ParsedClass, ParsedFile, ParsedFunction

# Source roots stripped when computing a file's importable dotted name.
_ROOT_PREFIXES = ("", "src/", "lib/", "app/")
_INIT_SUFFIX = "/__init__"


class PyImportResolver:
    """Resolves Python import statements to repo-relative file paths.

    Best-effort: it indexes every ``.py`` file under common source roots and
    maps dotted module names back to files. Imports that don't resolve to a
    repo file (third-party/stdlib) are simply dropped.
    """

    def __init__(self, files: set[str]) -> None:
        self.files = files
        self.index: dict[str, str] = {}
        for path in files:
            if not path.endswith(".py"):
                continue
            noext = path[:-3]
            for prefix in _ROOT_PREFIXES:
                if not noext.startswith(prefix):
                    continue
                rel = noext[len(prefix) :]
                if rel.endswith(_INIT_SUFFIX):
                    rel = rel[: -len(_INIT_SUFFIX)]
                dotted = rel.replace("/", ".")
                if dotted:
                    self.index.setdefault(dotted, path)

    def _lookup(self, parts: list[str]) -> str | None:
        joined = "/".join(parts)
        for candidate in (f"{joined}.py", f"{joined}/__init__.py"):
            if candidate in self.files:
                return candidate
        return None

    def resolve(
        self, module: str | None, level: int, names: list[str], current_path: str
    ) -> list[str]:
        if level == 0:
            if module and module in self.index:
                return [self.index[module]]
            return []

        # Relative import: walk up from the current file's package.
        dir_parts = current_path.split("/")[:-1]
        up = level - 1
        base = dir_parts[: len(dir_parts) - up] if up <= len(dir_parts) else []
        if module:
            target = self._lookup(base + module.split("."))
            return [target] if target else []
        resolved = [self._lookup(base + [name]) for name in names]
        return [r for r in resolved if r]


def parse_python_file(path: str, source: str, resolver: PyImportResolver) -> ParsedFile | None:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None

    pf = ParsedFile(path=path, language="Python")
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                pf.imports.extend(resolver.resolve(alias.name, 0, [], path))
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
            pf.imports.extend(resolver.resolve(node.module, node.level or 0, names, path))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            pf.functions.append(_parse_function(node))
        elif isinstance(node, ast.ClassDef):
            pf.classes.append(_parse_class(node))

    pf.imports = sorted(set(pf.imports) - {path})
    return pf


def _call_names(node: ast.AST) -> list[str]:
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return calls


def _parse_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ParsedFunction:
    return ParsedFunction(name=node.name, line=node.lineno, calls=_call_names(node))


def _base_name(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _parse_class(node: ast.ClassDef) -> ParsedClass:
    bases = [name for base in node.bases if (name := _base_name(base))]
    methods = [
        _parse_function(item)
        for item in node.body
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    # Python has no separate "implements"; all bases are treated as extends.
    return ParsedClass(name=node.name, line=node.lineno, bases=bases, methods=methods)
