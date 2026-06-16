"""Scanner protocol and the shared repository context.

A :class:`Scanner` inspects a repository and contributes to a
:class:`~repointel.models.Fingerprint`. Phase 10 will let third parties ship
scanners as plugins; the protocol here is the seam that makes that possible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from repointel.models import Dependency, Fingerprint

# Directories that never carry useful signal and are expensive to walk.
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "build",
        "dist",
        "coverage",
        ".venv",
        "venv",
        "__pycache__",
        ".dart_tool",
        ".idea",
        ".vscode",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".repointel",
        "vendor",
        "target",
    }
)

# Source-file extensions mapped to a canonical language name. Used for the
# primary-language heuristic. Config/markup extensions are intentionally absent.
CODE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".dart": "Dart",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
}


class RepoContext:
    """Cached, read-only view over a repository root.

    Scanners share one instance so file reads and the directory walk happen
    once per analysis.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._text_cache: dict[str, str | None] = {}
        self._language_stats: dict[str, int] | None = None
        self._source_dirs: set[str] | None = None
        self._files: list[tuple[str, int]] | None = None
        self._dirs: set[str] | None = None

    def exists(self, rel: str) -> bool:
        """Whether ``rel`` exists relative to the repo root."""
        return (self.root / rel).exists()

    def read_text(self, rel: str) -> str | None:
        """Read a file relative to the root, returning ``None`` if absent/unreadable."""
        if rel not in self._text_cache:
            target = self.root / rel
            try:
                self._text_cache[rel] = target.read_text(encoding="utf-8", errors="ignore")
            except (OSError, ValueError):
                self._text_cache[rel] = None
        return self._text_cache[rel]

    def language_stats(self) -> dict[str, int]:
        """Count source files per language, skipping ignored directories."""
        if self._language_stats is None:
            self._walk()
        assert self._language_stats is not None
        return self._language_stats

    def source_dirs(self) -> set[str]:
        """Relative directory paths (posix-style) that directly contain source files.

        Includes ``"."`` when the repository root itself holds source files.
        """
        if self._source_dirs is None:
            self._walk()
        assert self._source_dirs is not None
        return self._source_dirs

    def files(self) -> list[tuple[str, int]]:
        """Every non-ignored file as ``(relative_posix_path, size_bytes)``."""
        if self._files is None:
            self._walk()
        assert self._files is not None
        return self._files

    def directories(self) -> set[str]:
        """Every non-ignored directory as a relative posix path."""
        if self._dirs is None:
            self._walk()
        assert self._dirs is not None
        return self._dirs

    def _walk(self) -> None:
        stats: dict[str, int] = {}
        source_dirs: set[str] = set()
        files: list[tuple[str, int]] = []
        dirs: set[str] = set()
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root)
            if any(part in IGNORED_DIRS for part in rel.parts):
                continue
            rel_posix = rel.as_posix()
            if path.is_dir():
                dirs.add(rel_posix)
                continue
            if path.is_file():
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                files.append((rel_posix, size))
                lang = CODE_EXTENSIONS.get(path.suffix.lower())
                if lang:
                    stats[lang] = stats.get(lang, 0) + 1
                    source_dirs.add(path.parent.relative_to(self.root).as_posix())
        self._language_stats = stats
        self._source_dirs = source_dirs
        self._files = files
        self._dirs = dirs


@runtime_checkable
class Scanner(Protocol):
    """Inspects a repo and contributes to a fingerprint."""

    name: str

    def matches(self, ctx: RepoContext) -> bool:
        """Whether this scanner recognizes the repository."""
        ...

    def fingerprint(self, ctx: RepoContext, fp: Fingerprint) -> None:
        """Fill in fingerprint fields. Only called when :meth:`matches` is true."""
        ...

    def dependencies(self, ctx: RepoContext) -> list[Dependency]:
        """Declared third-party dependencies. Only called when :meth:`matches` is true."""
        ...

    def entry_points(self, ctx: RepoContext) -> list[str]:
        """Repo-relative entry-point files/commands. Only called when matched."""
        ...
