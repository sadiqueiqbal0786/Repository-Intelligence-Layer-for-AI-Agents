"""Repository-memory compression (Phase 12, foundations from Phase 4/5).

Squeezes the full analysis into a small token budget so an agent can load a
whole repo's understanding in one shot for a few thousand tokens. The
:class:`ContextPack` is curated from the derived memory — identity, counts, key
files, layers, conventions, top dependencies, decisions, and a history line —
deliberately excluding the heavy raw layers (full inventory, graph, cache).
"""

from __future__ import annotations

from math import ceil
from pathlib import Path

from repointel.models import (
    ArchitectureSummary,
    ContextPack,
    Conventions,
    Knowledge,
    ModulesDoc,
    RepositoryInventory,
    RepoSummary,
)

# A standard rough heuristic: ~4 characters per token for English/code text.
_CHARS_PER_TOKEN = 4

_ENTRY_LIMIT = 10
_KEY_FILE_LIMIT = 10
_DEP_LIMIT = 15
_DECISION_LIMIT = 15


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text`` (~4 chars/token)."""
    return estimate_tokens_for_chars(len(text))


def estimate_tokens_for_chars(char_count: int) -> int:
    return ceil(char_count / _CHARS_PER_TOKEN)


def build_context_pack(
    repo: RepoSummary,
    architecture: ArchitectureSummary,
    modules: ModulesDoc,
    conventions: Conventions,
    knowledge: Knowledge,
    inventory: RepositoryInventory,
) -> ContextPack:
    """Assemble the compact context pack from derived memory."""
    fp = repo.fingerprint
    return ContextPack(
        name=repo.name,
        language=fp.language,
        framework=fp.framework,
        architecture=fp.architecture,
        package_manager=fp.package_manager,
        file_count=repo.file_count,
        module_count=repo.module_count,
        total_loc=repo.total_loc,
        dependency_count=repo.dependency_count,
        entry_points=list(repo.entry_points[:_ENTRY_LIMIT]),
        key_files=list(architecture.key_files[:_KEY_FILE_LIMIT]),
        layers=[f"{layer.name} ({layer.file_count} files)" for layer in architecture.layers],
        class_naming=conventions.naming.classes,
        function_naming=conventions.naming.functions,
        dependency_injection=conventions.dependency_injection,
        patterns=[p.name for p in knowledge.patterns],
        testing=conventions.testing.framework,
        top_dependencies=_top_dependencies(inventory),
        decisions=[d.title for d in knowledge.decisions[:_DECISION_LIMIT]],
        history=_history_line(knowledge),
        confidence=repo.coverage.confidence if repo.coverage else None,
        warnings=list(repo.coverage.warnings) if repo.coverage else [],
    )


def context_pack(root: Path) -> ContextPack | None:
    """Load (building if needed) and assemble the context pack for ``root``."""
    from repointel.context.memory import build_memory, persist_memory
    from repointel.scanners import resolve_project_root
    from repointel.storage.json import (
        read_architecture,
        read_conventions,
        read_knowledge,
        read_modules,
        read_repo_summary,
        read_repository,
    )

    root = resolve_project_root(Path(root))
    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), root)

    repo = read_repo_summary(root)
    inventory = read_repository(root)
    if repo is None or inventory is None:
        return None
    return build_context_pack(
        repo,
        read_architecture(root) or ArchitectureSummary(),
        read_modules(root) or ModulesDoc(path=str(root)),
        read_conventions(root) or Conventions(),
        read_knowledge(root) or Knowledge(),
        inventory,
    )


def render_context_markdown(pack: ContextPack) -> str:
    """Render the pack as compact markdown — the form an agent reads."""
    lines = [f"# {pack.name}", ""]
    identity = _join(
        [
            ("Language", pack.language),
            ("Framework", pack.framework),
            ("Architecture", pack.architecture),
            ("Package manager", pack.package_manager),
        ]
    )
    if identity:
        lines.append(identity)
    lines.append(
        f"{pack.file_count} files · {pack.module_count} modules · "
        f"{pack.total_loc} LOC · {pack.dependency_count} deps"
    )
    if pack.confidence:
        lines.append(f"Graph confidence: {pack.confidence}")
    for warning in pack.warnings:
        lines.append(f"⚠️ {warning}")

    conventions = _join(
        [
            ("Classes", pack.class_naming),
            ("Functions", pack.function_naming),
            ("DI", pack.dependency_injection),
            ("Testing", pack.testing),
        ]
    )
    if conventions:
        lines += ["", "## Conventions", conventions]
    if pack.patterns:
        lines += ["", "## Patterns", ", ".join(pack.patterns)]
    _section(lines, "Layers", pack.layers)
    _section(lines, "Key files", pack.key_files)
    _section(lines, "Top dependencies", pack.top_dependencies)
    _section(lines, "Entry points", pack.entry_points)
    _section(lines, "Decisions", pack.decisions)
    if pack.history:
        lines += ["", "## History", pack.history]
    return "\n".join(lines) + "\n"


def _top_dependencies(inventory: RepositoryInventory) -> list[str]:
    # Runtime deps first (dev deps are noisier signal), de-duplicated by name.
    names: list[str] = []
    for dep in sorted(inventory.dependencies, key=lambda d: (d.dev, d.name.lower())):
        if dep.name not in names:
            names.append(dep.name)
    return names[:_DEP_LIMIT]


def _history_line(knowledge: Knowledge) -> str | None:
    history = knowledge.history
    if not history.is_git:
        return None
    return (
        f"{history.total_commits} commits, {history.contributor_count} contributors "
        f"({history.first_commit_date or '?'} → {history.last_commit_date or '?'})"
    )


def _join(pairs: list[tuple[str, str | None]]) -> str:
    return " · ".join(f"{label}: {value}" for label, value in pairs if value)


def _section(lines: list[str], title: str, items: list[str]) -> None:
    if items:
        lines += ["", f"## {title}", ", ".join(items)]


__all__ = [
    "build_context_pack",
    "context_pack",
    "estimate_tokens",
    "estimate_tokens_for_chars",
    "render_context_markdown",
]
