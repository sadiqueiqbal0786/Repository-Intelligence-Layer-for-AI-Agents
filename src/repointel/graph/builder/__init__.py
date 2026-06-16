"""Architecture-graph builder (Phase 3).

Two passes: parse every source file into the :mod:`parsed` IR, then assemble
nodes and edges — resolving name-based edges (extends/implements/calls) against
global indices once all nodes exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from repointel.graph.builder.parsed import ParsedFile, ParsedFunction
from repointel.models import ArchitectureGraph, GraphEdge, GraphNode, RepositoryInventory

if TYPE_CHECKING:
    from repointel.plugins import PluginRegistry


def build_graph(
    root: Path,
    inventory: RepositoryInventory,
    *,
    parse_cache: dict[str, ParsedFile] | None = None,
    registry: PluginRegistry | None = None,
) -> ArchitectureGraph:
    """Build the architecture graph for ``root`` from its inventory.

    ``parse_cache`` (Phase 7) maps repo-relative paths to already-parsed IR for
    files known to be unchanged; those files skip the read + parse step.
    ``registry`` (Phase 10) supplies the language parsers; defaults to the
    process-wide plugin registry.
    """
    parsed = parse_sources(root, inventory, parse_cache=parse_cache, registry=registry)
    return assemble_graph(inventory, parsed)


def parse_sources(
    root: Path,
    inventory: RepositoryInventory,
    *,
    parse_cache: dict[str, ParsedFile] | None = None,
    registry: PluginRegistry | None = None,
) -> list[ParsedFile]:
    """Parse every parseable source file into the :mod:`parsed` IR.

    A parser is looked up per file language via the plugin registry (Phase 10),
    so new languages are added as plugins, not as branches here. Reuses
    ``parse_cache`` entries for unchanged files; reads and parses the rest. The
    caller guarantees cache entries are only supplied when valid (the set of
    source files is unchanged — see :mod:`repointel.context.incremental`).
    """
    if registry is None:
        from repointel.plugins import default_registry

        registry = default_registry()

    root = Path(root)
    file_set = {f.path for f in inventory.files}
    resolvers: dict[str, object] = {}

    parsed: list[ParsedFile] = []
    for entry in inventory.files:
        parser = registry.parser_for(entry.language)
        if parser is None:
            continue
        if parse_cache is not None and entry.path in parse_cache:
            parsed.append(parse_cache[entry.path])
            continue
        resolver = resolvers.get(parser.language)
        if resolver is None:
            resolver = parser.make_resolver(file_set, root)
            resolvers[parser.language] = resolver
        try:
            source = (root / entry.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        pf = parser.parse(entry.path, source, resolver)
        if pf is not None:
            parsed.append(pf)
    return parsed


def assemble_graph(inventory: RepositoryInventory, parsed: list[ParsedFile]) -> ArchitectureGraph:
    """Assemble the graph from the inventory's structure and parsed IR.

    Pure in-memory work — the expensive I/O happens in :func:`parse_sources`.
    """
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
