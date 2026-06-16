"""Incremental build cache (Phase 7).

``cache.json`` records, per source file, a cheap change signature (size + mtime)
plus the expensive-to-recompute results: its line count and parsed IR. On the
next build the engine reuses these for files whose signature is unchanged, so
only the files that actually changed are re-read and re-parsed.

The cache is an internal optimization — it is *not* part of the agent-facing
memory manifest in ``repo.json``. A missing or stale cache only costs a full
rebuild; it can never produce a wrong result.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from repointel.graph.builder.parsed import ParsedFile
from repointel.models import RepositoryInventory

CACHE_SCHEMA_VERSION = 1


class CachedFile(BaseModel):
    """Cached analysis for a single source file."""

    size: int
    mtime: float
    loc: int = 0
    language: str | None = None
    # Parsed IR, present only for languages the graph builder parses (Python/Dart).
    parsed: ParsedFile | None = None


class BuildCache(BaseModel):
    """The whole cache: source-file path -> :class:`CachedFile`."""

    schema_version: int = CACHE_SCHEMA_VERSION
    files: dict[str, CachedFile] = Field(default_factory=dict)

    def signature(self, path: str) -> tuple[int, float] | None:
        entry = self.files.get(path)
        return (entry.size, entry.mtime) if entry else None


def build_cache(
    root: Path, inventory: RepositoryInventory, parsed: list[ParsedFile]
) -> BuildCache:
    """Assemble a fresh cache from a completed build.

    Stats each source file once for its current signature; reads nothing.
    """
    root = Path(root)
    parsed_by_path = {pf.path: pf for pf in parsed}
    files: dict[str, CachedFile] = {}
    for entry in inventory.files:
        if not entry.language:
            continue
        try:
            st = (root / entry.path).stat()
        except OSError:
            continue
        files[entry.path] = CachedFile(
            size=st.st_size,
            mtime=st.st_mtime,
            loc=entry.loc,
            language=entry.language,
            parsed=parsed_by_path.get(entry.path),
        )
    return BuildCache(files=files)


__all__ = ["CACHE_SCHEMA_VERSION", "BuildCache", "CachedFile", "build_cache"]
