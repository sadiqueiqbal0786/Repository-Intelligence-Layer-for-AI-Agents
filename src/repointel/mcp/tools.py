"""Repository-intelligence tools (Phase 5), as plain functions.

These read from the ``.repointel/`` memory layer (building it on first use if
absent) and return JSON-serializable dicts. They deliberately do **not** import
the MCP SDK — :mod:`repointel.mcp.server` wraps them — so they stay unit-testable
and usable as a plain library API.
"""

from __future__ import annotations

from pathlib import Path

from repointel.context.compression import context_pack
from repointel.context.explanation import available_modules, resolve_module
from repointel.context.explanation import explain as explain_target
from repointel.context.impact import analyze_impact as analyze_impact_target
from repointel.context.impact import impact_candidates
from repointel.context.memory import build_memory, persist_memory
from repointel.storage.json import (
    read_architecture,
    read_conventions,
    read_graph,
    read_knowledge,
    read_modules,
    read_repo_summary,
    read_repository,
)


def ensure_memory(root: Path) -> None:
    """Build and persist repository memory if it hasn't been built yet."""
    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), Path(root))


def get_context(root: Path) -> dict:
    """The compact context pack: a whole repo's understanding in one call.

    Identity, counts, key files, layers, conventions, top dependencies, recorded
    decisions, and a history line — the most token-efficient way for an agent to
    understand the repository. Start here.
    """
    ensure_memory(root)
    pack = context_pack(root)
    assert pack is not None
    return pack.model_dump()


def get_project_summary(root: Path) -> dict:
    """Project identity: language, framework, package manager, counts, entry points."""
    ensure_memory(root)
    repo = read_repo_summary(root)
    assert repo is not None
    summary = repo.model_dump()
    if conventions := read_conventions(root):
        summary["conventions"] = conventions.model_dump()
    return summary


def get_architecture(root: Path) -> dict:
    """The system's shape: style, layers, languages, frameworks, key files."""
    ensure_memory(root)
    architecture = read_architecture(root)
    assert architecture is not None
    return architecture.model_dump()


def get_knowledge(root: Path) -> dict:
    """The knowledge layer: architecture decisions, patterns, and project history."""
    ensure_memory(root)
    knowledge = read_knowledge(root)
    assert knowledge is not None
    return knowledge.model_dump()


def get_conventions(root: Path) -> dict:
    """How the team writes code: naming styles, layering, DI, testing, patterns."""
    ensure_memory(root)
    conventions = read_conventions(root)
    assert conventions is not None
    return conventions.model_dump()


def get_module_info(root: Path, module: str | None = None) -> dict:
    """Details for one module, or the module list when ``module`` is omitted."""
    ensure_memory(root)
    doc = read_modules(root)
    assert doc is not None

    if module is None:
        return {
            "modules": [
                {"path": m.path, "language": m.language, "file_count": m.file_count, "loc": m.loc}
                for m in doc.modules
            ]
        }

    match = _find_module(doc.modules, module)
    if match is None:
        return {
            "error": f"module '{module}' not found",
            "available": [m.path for m in doc.modules],
        }
    return match.model_dump()


def get_dependencies(root: Path) -> dict:
    """Declared third-party dependencies, with versions and dev flags."""
    ensure_memory(root)
    inventory = read_repository(root)
    assert inventory is not None
    return {
        "count": len(inventory.dependencies),
        "dependencies": [d.model_dump() for d in inventory.dependencies],
    }


def explain_module(root: Path, target: str) -> dict:
    """Explain a module: purpose, dependencies, consumers, critical files, risk.

    Generated from repository memory without an LLM. Returns an ``error`` with
    the available module list when ``target`` doesn't match.
    """
    ensure_memory(root)
    explanation = explain_target(root, target)
    if explanation is None:
        return {
            "error": f"module '{target}' not found",
            "available": available_modules(root),
        }
    return explanation.model_dump()


def analyze_impact(root: Path, target: str) -> dict:
    """Predict the impact of changing a file: blast radius, affected modules, risk.

    Generated from the graph without an LLM. Returns an ``error`` with candidate
    files when ``target`` is ambiguous or unknown.
    """
    ensure_memory(root)
    report = analyze_impact_target(root, target)
    if report is None:
        return {
            "error": f"file '{target}' not found",
            "candidates": impact_candidates(root, target),
        }
    return report.model_dump()


def get_health(root: Path) -> dict:
    """Report how much of the repo the graph actually resolved.

    A fail-loud trust signal: overall ``confidence``, how many graphed source
    files are connected vs. isolated, per-language coverage (graphed vs.
    inventory-only), and human-readable ``warnings``. Consult this before
    trusting a "safe to change" / "no consumers" verdict — low confidence means
    imports may be unresolved and those verdicts under-report.
    """
    from repointel.context.staleness import assess_staleness

    ensure_memory(root)
    repo = read_repo_summary(root)
    assert repo is not None
    health = (
        repo.coverage.model_dump()
        if repo.coverage is not None
        else {"confidence": "unknown", "warnings": [], "languages": []}
    )
    health["freshness"] = assess_staleness(Path(root), repo.built_at_commit)
    return health


def get_critical_files(root: Path, limit: int = 10) -> dict:
    """The most-depended-on files (highest import in-degree) — the risk hotspots."""
    ensure_memory(root)
    graph = read_graph(root)
    assert graph is not None

    in_degree: dict[str, int] = {}
    for edge in graph.edges:
        if edge.kind == "imports":
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
    id_to_path = {n.id: n.path for n in graph.nodes if n.path}

    ranked = sorted(
        ((id_to_path[nid], count) for nid, count in in_degree.items() if nid in id_to_path),
        key=lambda item: (-item[1], item[0]),
    )
    return {
        "critical_files": [
            {"path": path, "imported_by": count} for path, count in ranked[:limit]
        ]
    }


def _find_module(modules: list, query: str):
    """Match a module by exact path, basename, or path suffix.

    Delegates to the shared resolver so ``get_module_info`` prefers real source
    over test/spec dirs exactly like ``explain_module`` does.
    """
    return resolve_module(modules, query)


__all__ = [
    "analyze_impact",
    "ensure_memory",
    "explain_module",
    "get_architecture",
    "get_context",
    "get_conventions",
    "get_critical_files",
    "get_dependencies",
    "get_health",
    "get_knowledge",
    "get_module_info",
    "get_project_summary",
]
