"""Tests for the Phase 10 plugin ecosystem."""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder import build_graph
from repointel.graph.builder.parsed import ParsedClass, ParsedFile, ParsedFunction
from repointel.plugins import (
    Plugin,
    PluginRegistry,
    default_registry,
    discover_plugins,
    register_plugin,
)
from repointel.plugins.builtin import builtin_plugins
from repointel.scanners import scan_repo


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


# --- an example third-party parser plugin, defined inline ---------------------

_GO_FUNC_RE = re.compile(r"(?m)^func\s+([A-Za-z_]\w*)\s*\(")
_GO_STRUCT_RE = re.compile(r"(?m)^type\s+([A-Za-z_]\w*)\s+struct\b")


class GoParser:
    language = "Go"

    def make_resolver(self, files: set[str], root: Path) -> set[str]:
        return files

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        pf = ParsedFile(path=path, language="Go")
        pf.classes = [ParsedClass(name=m.group(1), line=1) for m in _GO_STRUCT_RE.finditer(source)]
        pf.functions = [
            ParsedFunction(name=m.group(1), line=1) for m in _GO_FUNC_RE.finditer(source)
        ]
        return pf


go_plugin = Plugin(name="go", parser=GoParser())


# --- registry behavior --------------------------------------------------------


def test_builtin_registry_has_python_and_dart() -> None:
    registry = default_registry()
    assert registry.parseable_languages() == {"Python", "Dart"}
    assert registry.parser_for("Python") is not None
    assert registry.parser_for("Dart") is not None
    assert registry.parser_for("Go") is None
    assert registry.parser_for(None) is None
    # Python + Dart ecosystem scanners are exposed.
    assert len(registry.scanners()) >= 2


def test_register_inserts_at_front_and_wins() -> None:
    registry = PluginRegistry(builtin_plugins())
    assert registry.parser_for("Go") is None
    registry.register(go_plugin)
    assert isinstance(registry.parser_for("Go"), GoParser)


def test_discover_plugins_never_raises() -> None:
    # No entry points installed in the test env -> empty, but must not error.
    assert isinstance(discover_plugins(), list)


# --- end-to-end: a plugin extends graphing without core changes ---------------


def test_core_does_not_graph_go_without_a_plugin(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "main.go", "package main\n\ntype Server struct {}\n\nfunc Run() {}\n")
    inventory = scan_repo(tmp_path)
    graph = build_graph(tmp_path, inventory)  # default registry, no Go parser
    code_nodes = [n for n in graph.nodes if n.kind in {"class", "function"}]
    assert not any(n.language == "Go" for n in code_nodes)


def test_custom_parser_plugin_graphs_a_new_language(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(tmp_path, "main.go", "package main\n\ntype Server struct {}\n\nfunc Run() {}\n")
    inventory = scan_repo(tmp_path)

    registry = PluginRegistry([*builtin_plugins(), go_plugin])
    graph = build_graph(tmp_path, inventory, registry=registry)

    names = {n.name for n in graph.nodes}
    assert "Server" in names  # struct -> class node
    assert "Run" in names  # func -> function node


def test_register_plugin_affects_default_registry() -> None:
    try:
        register_plugin(go_plugin)
        assert default_registry().parser_for("Go") is not None
    finally:
        default_registry.cache_clear()  # restore a clean process-wide registry
