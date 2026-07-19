"""Incremental intelligence (Phase 7).

Updates repository memory by re-reading and re-parsing only the source files
that changed since the last build, instead of the whole tree. The cheap signal
is each file's ``(size, mtime)`` signature, recorded in ``.repointel/cache.json``
by the previous build.

Correctness model
-----------------
- **Line counts** are local to a file, so the count for any unchanged file is
  always safe to reuse.
- **Parsed IR** carries *resolved* import targets, which depend on the set of
  files that exist. Reusing it for an unchanged file is therefore only valid
  while that set is unchanged — i.e. when no parseable source file was added or
  deleted. When one is, we re-parse everything (still correct, just not the fast
  path); pure edits to existing files take the fast path.

A missing or unreadable cache simply triggers a full :func:`build_memory`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from repointel.context.memory import MemoryBundle, _assemble_bundle, build_memory
from repointel.graph.builder import assemble_graph, parse_sources
from repointel.plugins import default_registry
from repointel.scanners import RepoContext, resolve_project_root, scan_repo
from repointel.scanners.base import CODE_EXTENSIONS
from repointel.storage.json import read_cache


@dataclass
class ChangeSet:
    """What changed since the last build."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0
    full_rebuild: bool = False

    @property
    def changed_count(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)

    @property
    def has_changes(self) -> bool:
        return self.full_rebuild or self.changed_count > 0


def update_memory(root: Path) -> tuple[MemoryBundle, ChangeSet]:
    """Rebuild memory incrementally; fall back to a full build with no cache.

    Returns the fresh :class:`MemoryBundle` (not yet persisted) and the
    :class:`ChangeSet` describing what moved.
    """
    root = resolve_project_root(Path(root))
    previous = read_cache(root)
    if previous is None:
        return build_memory(root), ChangeSet(full_rebuild=True)

    current = _current_code_signatures(root)
    prev = previous.files

    def is_same(path: str) -> bool:
        entry = prev.get(path)
        return entry is not None and current[path] == (entry.size, entry.mtime)

    added = sorted(p for p in current if p not in prev)
    deleted = sorted(p for p in prev if p not in current)
    modified = sorted(p for p in current if p in prev and not is_same(p))
    unchanged = [p for p in current if is_same(p)]

    loc_cache = {p: prev[p].loc for p in unchanged}

    # Parsed-IR reuse is only sound while the parseable file set is stable. The
    # set of parseable languages comes from the active plugins (Phase 10).
    parseable = default_registry().parseable_languages()
    file_set_changed = any(_language(p) in parseable for p in added + deleted)
    parse_cache = None
    if not file_set_changed:
        parse_cache = {
            p: prev[p].parsed for p in unchanged if prev[p].parsed is not None
        }

    inventory = scan_repo(root, loc_cache=loc_cache)
    parsed = parse_sources(root, inventory, parse_cache=parse_cache)
    graph = assemble_graph(inventory, parsed)
    bundle = _assemble_bundle(root, inventory, graph, parsed)

    changeset = ChangeSet(
        added=added, modified=modified, deleted=deleted, unchanged=len(unchanged)
    )
    return bundle, changeset


def _current_code_signatures(root: Path) -> dict[str, tuple[int, float]]:
    """``(size, mtime)`` for every current source file — a stat-only walk."""
    signatures = RepoContext(Path(root)).signatures()
    return {path: sig for path, sig in signatures.items() if _language(path) is not None}


def _language(path: str) -> str | None:
    return CODE_EXTENSIONS.get(PurePosixPath(path).suffix.lower())


__all__ = ["ChangeSet", "update_memory"]
