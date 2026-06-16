"""Module/repository summary generation.

Phase 4 derives ``modules.json`` here. Phase 8 (Explanation Engine) will add
purpose / critical-paths / risks narratives on top of these structures.
"""

from __future__ import annotations

from repointel.models import (
    ArchitectureGraph,
    ModulesDoc,
    ModuleSummary,
    RepositoryInventory,
)


def _module_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


def summarize_modules(inventory: RepositoryInventory, graph: ArchitectureGraph) -> ModulesDoc:
    """Derive ``modules.json`` — per-module files, sizes, and inter-module imports."""
    # LOC and file lists per module, from the inventory.
    loc_by_module: dict[str, int] = {}
    files_by_module: dict[str, list[str]] = {}
    for entry in inventory.files:
        if not entry.language:
            continue
        module = _module_of(entry.path)
        loc_by_module[module] = loc_by_module.get(module, 0) + entry.loc
        files_by_module.setdefault(module, []).append(entry.path)

    # Class/function counts per module, from graph nodes.
    classes_by_module: dict[str, int] = {}
    functions_by_module: dict[str, int] = {}
    for node in graph.nodes:
        if node.kind == "class" and node.path:
            module = _module_of(node.path)
            classes_by_module[module] = classes_by_module.get(module, 0) + 1
        elif node.kind == "function" and node.path:
            module = _module_of(node.path)
            functions_by_module[module] = functions_by_module.get(module, 0) + 1

    # Inter-module imports, aggregated from file-level import edges.
    file_to_module = {
        n.path: _module_of(n.path) for n in graph.nodes if n.kind == "file" and n.path
    }
    imports_by_module: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.kind != "imports":
            continue
        src = edge.source.removeprefix("file:")
        tgt = edge.target.removeprefix("file:")
        src_mod = file_to_module.get(src)
        tgt_mod = file_to_module.get(tgt)
        if src_mod and tgt_mod and src_mod != tgt_mod:
            imports_by_module.setdefault(src_mod, set()).add(tgt_mod)

    summaries: list[ModuleSummary] = []
    for module in inventory.modules:
        summaries.append(
            ModuleSummary(
                path=module.path,
                language=module.language,
                file_count=module.file_count,
                loc=loc_by_module.get(module.path, 0),
                classes=classes_by_module.get(module.path, 0),
                functions=functions_by_module.get(module.path, 0),
                files=sorted(files_by_module.get(module.path, [])),
                imports=sorted(imports_by_module.get(module.path, set())),
            )
        )
    return ModulesDoc(path=inventory.path, modules=summaries)


__all__ = ["summarize_modules"]
