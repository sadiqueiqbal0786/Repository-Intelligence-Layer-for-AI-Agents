"""Explanation engine (Phase 8).

Generates structured, **LLM-free** explanations of a module straight from
repository memory: its purpose (inferred from structure + naming), what it
depends on, who depends on it, its most-critical files, and a derived risk
assessment for changing it.

Everything here is a deterministic read over the graph and summaries — the same
inputs always yield the same explanation.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from repointel.context.memory import build_memory, persist_memory
from repointel.graph.builder import file_id
from repointel.graph.traversal import GraphView
from repointel.models import (
    ArchitectureGraph,
    ModuleExplanation,
    ModulesDoc,
    ModuleSummary,
    RepositoryInventory,
)
from repointel.scanners import resolve_project_root
from repointel.storage.json import (
    read_graph,
    read_modules,
    read_repo_summary,
    read_repository,
)

# Class-name suffix -> the role it signals. Order matters: first match wins.
_ROLE_SUFFIXES: list[tuple[str, str]] = [
    ("Controller", "handles incoming requests and routing"),
    ("Handler", "handles incoming requests or events"),
    ("Service", "encapsulates service-layer business logic"),
    ("UseCase", "orchestrates an application use case"),
    ("Repository", "provides data access and persistence"),
    ("Repo", "provides data access and persistence"),
    ("Dao", "provides data access and persistence"),
    ("Provider", "provides state or dependency wiring"),
    ("Notifier", "manages and broadcasts state changes"),
    ("Widget", "defines user-interface widgets"),
    ("View", "renders views or screens"),
    ("Page", "renders views or screens"),
    ("Schema", "defines data schemas"),
    ("Dto", "defines data-transfer objects"),
    ("Entity", "defines domain entities"),
    ("Model", "defines domain models and data structures"),
]

_CRITICAL_FILE_LIMIT = 5
_KEY_CLASS_LIMIT = 12


def explain(root: Path, target: str) -> ModuleExplanation | None:
    """Explain ``target`` (a module path/name) for the repo at ``root``.

    Builds memory on first use; returns ``None`` if no module matches.
    """
    root = resolve_project_root(Path(root))
    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), root)

    modules = read_modules(root)
    graph = read_graph(root)
    inventory = read_repository(root)
    if modules is None or graph is None or inventory is None:
        return None
    return build_explanation(target, modules, graph, inventory)


def available_modules(root: Path) -> list[str]:
    """Module paths an :func:`explain` query can resolve against."""
    doc = read_modules(resolve_project_root(Path(root)))
    return [m.path for m in doc.modules] if doc else []


def build_explanation(
    target: str,
    modules: ModulesDoc,
    graph: ArchitectureGraph,
    inventory: RepositoryInventory,
) -> ModuleExplanation | None:
    """Assemble an explanation from already-loaded memory (pure function)."""
    module = resolve_module(modules.modules, target)
    if module is None:
        return None

    own_files = set(module.files)
    view = GraphView(graph)

    dependencies = list(module.imports)
    consumers = sorted(m.path for m in modules.modules if module.path in m.imports)
    key_classes = sorted(
        {n.name for n in graph.nodes if n.kind == "class" and n.path in own_files}
    )
    critical_files = _critical_files(graph, own_files)
    blast_radius = _blast_radius(view, own_files)
    entry_points = [ep for ep in inventory.entry_points if ep in own_files]
    risk_level, risks = _assess_risk(module, consumers, blast_radius)

    return ModuleExplanation(
        target=target,
        module=module.path,
        language=module.language,
        purpose=_purpose(module, key_classes),
        file_count=module.file_count,
        class_count=module.classes,
        function_count=module.functions,
        loc=module.loc,
        key_classes=key_classes[:_KEY_CLASS_LIMIT],
        dependencies=dependencies,
        consumers=consumers,
        critical_files=critical_files,
        entry_points=entry_points,
        blast_radius=blast_radius,
        risk_level=risk_level,
        risks=risks,
    )


# Path segments that mark a directory as tests/specs rather than shippable
# source. A bare name like ``calendars`` frequently exists under BOTH ``lib/src``
# and ``test`` — resolving to the test copy yields a wrong explanation and a
# dangerously false "no internal consumers — safe to change" verdict.
_TEST_SEGMENTS: frozenset[str] = frozenset(
    {"test", "tests", "integration_test", "test_driver", "__tests__", "spec", "specs"}
)


def _is_test_path(path: str) -> bool:
    return any(seg in _TEST_SEGMENTS for seg in path.split("/"))


def resolve_module(modules: list[ModuleSummary], query: str) -> ModuleSummary | None:
    """Match a module by exact path, basename, or path suffix.

    When several modules match a non-exact query, choose deterministically:
    real source before test/spec dirs, then the shallowest (most canonical)
    path, then lexical order. This keeps ``explain calendars`` on
    ``lib/src/calendars`` rather than an incidental ``test/calendars``. Shared
    with the MCP ``get_module_info`` tool so both resolve identically.
    """
    q = query.strip("/")
    for m in modules:
        if m.path == q:
            return m
    candidates = [
        m for m in modules if PurePosixPath(m.path).name == q or m.path.endswith(f"/{q}")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda m: (_is_test_path(m.path), m.path.count("/"), m.path))
    return candidates[0]


def _critical_files(graph: ArchitectureGraph, own_files: set[str]) -> list[str]:
    """The module's files with the most incoming ``imports`` edges."""
    in_degree: dict[str, int] = {}
    for edge in graph.edges:
        if edge.kind == "imports":
            target = edge.target.removeprefix("file:")
            in_degree[target] = in_degree.get(target, 0) + 1
    ranked = sorted(
        ((f, in_degree.get(f, 0)) for f in own_files),
        key=lambda item: (-item[1], item[0]),
    )
    return [f for f, count in ranked if count > 0][:_CRITICAL_FILE_LIMIT]


def _blast_radius(view: GraphView, own_files: set[str]) -> int:
    """How many files outside the module transitively import one of its files."""
    own_ids = {file_id(f) for f in own_files}
    reached: set[str] = set()
    for f in own_files:
        reached |= view.transitive_dependents(file_id(f))
    return len(reached - own_ids)


def _assess_risk(
    module: ModuleSummary, consumers: list[str], blast_radius: int
) -> tuple[str, list[str]]:
    risks: list[str] = []
    n_consumers = len(consumers)
    if n_consumers:
        risks.append(f"Imported by {n_consumers} other module(s) — changes ripple to consumers.")
    if blast_radius:
        risks.append(f"{blast_radius} file(s) transitively depend on this module.")
    if module.loc >= 1000:
        risks.append(f"Large module ({module.loc} LOC) widens the surface for regressions.")
    if not n_consumers and not blast_radius:
        risks.append("No internal consumers — likely safe to change in isolation.")

    if blast_radius >= 10 or n_consumers >= 5:
        level = "high"
    elif blast_radius >= 3 or n_consumers >= 2:
        level = "medium"
    else:
        level = "low"
    return level, risks


def _purpose(module: ModuleSummary, key_classes: list[str]) -> str:
    name = PurePosixPath(module.path).name if module.path != "." else "the root package"
    detail = (
        f"defines {module.classes} class(es) and {module.functions} function(s) "
        f"across {module.file_count} file(s)"
    )
    if module.language:
        detail = f"is written in {module.language} and {detail}"
    sentence = f"The `{name}` module {detail}."

    role = _infer_role(key_classes)
    if role:
        sentence += f" It primarily {role}."
    return sentence


def _infer_role(key_classes: list[str]) -> str | None:
    for suffix, phrase in _ROLE_SUFFIXES:
        if any(name.endswith(suffix) for name in key_classes):
            return phrase
    return None


__all__ = ["available_modules", "build_explanation", "explain", "resolve_module"]
