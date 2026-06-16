"""Architecture-graph builder (Phase 3).

Two passes: parse every source file into the :mod:`parsed` IR, then assemble
nodes and edges — resolving name-based edges (extends/implements/calls) against
global indices once all nodes exist.
"""

from __future__ import annotations

import re
from pathlib import Path

from repointel.graph.builder.dart import DartImportResolver, parse_dart_file
from repointel.graph.builder.parsed import ParsedFile, ParsedFunction
from repointel.graph.builder.python import PyImportResolver, parse_python_file
from repointel.models import ArchitectureGraph, GraphEdge, GraphNode, RepositoryInventory

_PARSED_LANGUAGES = {"Python", "Dart"}


def build_graph(root: Path, inventory: RepositoryInventory) -> ArchitectureGraph:
    """Build the architecture graph for ``root`` from its inventory."""
    root = Path(root)
    file_set = {f.path for f in inventory.files}
    py_resolver = PyImportResolver(file_set)
    dart_resolver = DartImportResolver(file_set, _dart_package_name(root))

    parsed: list[ParsedFile] = []
    for entry in inventory.files:
        if entry.language not in _PARSED_LANGUAGES:
            continue
        try:
            source = (root / entry.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if entry.language == "Python":
            pf = parse_python_file(entry.path, source, py_resolver)
        else:
            pf = parse_dart_file(entry.path, source, dart_resolver)
        if pf is not None:
            parsed.append(pf)

    builder = _GraphBuilder()
    _add_structure(builder, inventory)
    class_index, func_index = _add_code_elements(builder, parsed)
    _add_imports(builder, parsed)
    _add_inheritance(builder, parsed, class_index)
    _add_calls(builder, parsed, func_index)
    return builder.build(str(Path(inventory.path)))


# ---- id helpers --------------------------------------------------------------


def module_id(path: str) -> str:
    return f"module:{path}"


def file_id(path: str) -> str:
    return f"file:{path}"


def class_id(path: str, name: str) -> str:
    return f"class:{path}:{name}"


def function_id(path: str, qualname: str) -> str:
    return f"function:{path}:{qualname}"


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _parent_dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


# ---- assembly passes ---------------------------------------------------------


def _add_structure(builder: _GraphBuilder, inventory: RepositoryInventory) -> None:
    for module in inventory.modules:
        builder.add_node(
            module_id(module.path),
            "module",
            module.path or ".",
            path=module.path,
            language=module.language,
        )
    for entry in inventory.files:
        if not entry.language:
            continue
        builder.add_node(
            file_id(entry.path),
            "file",
            _basename(entry.path),
            path=entry.path,
            language=entry.language,
        )
        builder.add_edge(module_id(_parent_dir(entry.path)), file_id(entry.path), "contains")


def _add_code_elements(
    builder: _GraphBuilder, parsed: list[ParsedFile]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    class_index: dict[str, list[str]] = {}
    func_index: dict[str, list[str]] = {}

    for pf in parsed:
        fid = file_id(pf.path)
        for fn in pf.functions:
            nid = function_id(pf.path, fn.name)
            builder.add_node(
                nid, "function", fn.name, path=pf.path, line=fn.line, language=pf.language
            )
            builder.add_edge(fid, nid, "contains")
            func_index.setdefault(fn.name, []).append(nid)
        for cls in pf.classes:
            cid = class_id(pf.path, cls.name)
            builder.add_node(
                cid, "class", cls.name, path=pf.path, line=cls.line, language=pf.language
            )
            builder.add_edge(fid, cid, "contains")
            class_index.setdefault(cls.name, []).append(cid)
            for method in cls.methods:
                qual = f"{cls.name}.{method.name}"
                mid = function_id(pf.path, qual)
                builder.add_node(
                    mid, "function", qual, path=pf.path, line=method.line, language=pf.language
                )
                builder.add_edge(cid, mid, "contains")
    return class_index, func_index


def _add_imports(builder: _GraphBuilder, parsed: list[ParsedFile]) -> None:
    for pf in parsed:
        fid = file_id(pf.path)
        for target in pf.imports:
            builder.add_edge(fid, file_id(target), "imports")


def _add_inheritance(
    builder: _GraphBuilder, parsed: list[ParsedFile], class_index: dict[str, list[str]]
) -> None:
    for pf in parsed:
        for cls in pf.classes:
            cid = class_id(pf.path, cls.name)
            for base in cls.bases:
                if tid := _resolve_class(base, pf.path, cid, class_index):
                    builder.add_edge(cid, tid, "extends")
            for iface in cls.interfaces:
                if tid := _resolve_class(iface, pf.path, cid, class_index):
                    builder.add_edge(cid, tid, "implements")


def _add_calls(
    builder: _GraphBuilder, parsed: list[ParsedFile], func_index: dict[str, list[str]]
) -> None:
    def link(fn: ParsedFunction, caller_id: str) -> None:
        for callee in set(fn.calls):
            targets = func_index.get(callee)
            # Conservative: only link unambiguous, single-definition names.
            if targets and len(targets) == 1 and targets[0] != caller_id:
                builder.add_edge(caller_id, targets[0], "calls")

    for pf in parsed:
        for fn in pf.functions:
            link(fn, function_id(pf.path, fn.name))
        for cls in pf.classes:
            for method in cls.methods:
                link(method, function_id(pf.path, f"{cls.name}.{method.name}"))


def _resolve_class(
    name: str, current_path: str, self_id: str, class_index: dict[str, list[str]]
) -> str | None:
    candidates = [c for c in class_index.get(name, []) if c != self_id]
    if not candidates:
        return None
    same_file = [c for c in candidates if c.startswith(f"class:{current_path}:")]
    if same_file:
        return same_file[0]
    return candidates[0] if len(candidates) == 1 else None


def _dart_package_name(root: Path) -> str | None:
    pubspec = root / "pubspec.yaml"
    try:
        text = pubspec.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = re.search(r"(?m)^name:\s*(\S+)", text)
    return match.group(1) if match else None


# ---- accumulator -------------------------------------------------------------


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str, str], GraphEdge] = {}

    def add_node(
        self,
        node_id: str,
        kind: str,
        name: str,
        *,
        path: str | None = None,
        line: int | None = None,
        language: str | None = None,
    ) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(
                id=node_id, kind=kind, name=name, path=path, line=line, language=language
            )

    def add_edge(self, source: str, target: str, kind: str) -> None:
        self._edges[(source, target, kind)] = GraphEdge(source=source, target=target, kind=kind)

    def build(self, path: str) -> ArchitectureGraph:
        # Keep only edges whose endpoints both exist as nodes.
        edges = [
            e for e in self._edges.values() if e.source in self.nodes and e.target in self.nodes
        ]
        node_kinds: dict[str, int] = {}
        for node in self.nodes.values():
            node_kinds[node.kind] = node_kinds.get(node.kind, 0) + 1
        edge_kinds: dict[str, int] = {}
        for edge in edges:
            edge_kinds[edge.kind] = edge_kinds.get(edge.kind, 0) + 1
        nodes = list(self.nodes.values())
        return ArchitectureGraph(
            path=path,
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            node_kinds=node_kinds,
            edge_kinds=edge_kinds,
        )
