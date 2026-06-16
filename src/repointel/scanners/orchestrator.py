"""Orchestrators that turn a repo into a Fingerprint (Phase 1) or a full
RepositoryInventory (Phase 2), sharing a single :class:`RepoContext` walk.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from repointel.context.architecture import detect_architecture
from repointel.models import (
    Dependency,
    FileEntry,
    Fingerprint,
    Module,
    RepositoryInventory,
)
from repointel.scanners.base import CODE_EXTENSIONS, RepoContext
from repointel.scanners.registry import SCANNERS

# Well-known configuration files, matched by basename anywhere in the tree.
CONFIG_FILENAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "uv.lock",
        "pdm.lock",
        "pubspec.yaml",
        "pubspec.lock",
        "analysis_options.yaml",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "tsconfig.json",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Makefile",
        "go.mod",
        "go.sum",
        "Cargo.toml",
        "Cargo.lock",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        ".gitignore",
        ".env",
        ".env.example",
    }
)


def _apply_fingerprint(ctx: RepoContext, fp: Fingerprint) -> None:
    """Populate ``fp`` from the language scan, matching scanners, and architecture."""
    stats = ctx.language_stats()
    fp.languages = dict(sorted(stats.items(), key=lambda kv: kv[1], reverse=True))
    if fp.languages:
        primary = next(iter(fp.languages))
        fp.set("language", primary, f"{fp.languages[primary]} source files")

    for scanner in SCANNERS:
        if scanner.matches(ctx):
            scanner.fingerprint(ctx, fp)

    detect_architecture(ctx, fp)


def fingerprint_repo(root: Path) -> Fingerprint:
    """Analyze ``root`` and return its fingerprint (Phase 1)."""
    ctx = RepoContext(Path(root))
    fp = Fingerprint(path=str(ctx.root))
    _apply_fingerprint(ctx, fp)
    return fp


def scan_repo(root: Path) -> RepositoryInventory:
    """Build a complete inventory of ``root`` (Phase 2)."""
    ctx = RepoContext(Path(root))
    fp = Fingerprint(path=str(ctx.root))
    _apply_fingerprint(ctx, fp)

    files: list[FileEntry] = []
    total_loc = 0
    for rel, size in ctx.files():
        lang = CODE_EXTENSIONS.get(PurePosixPath(rel).suffix.lower())
        loc = 0
        if lang:
            text = ctx.read_text(rel)
            if text:
                loc = text.count("\n") + (0 if text.endswith("\n") else 1)
                total_loc += loc
        files.append(FileEntry(path=rel, language=lang, size=size, loc=loc))
    files.sort(key=lambda f: f.path)

    modules = _discover_modules(ctx)
    configs = sorted(rel for rel, _ in ctx.files() if _is_config(rel))
    directories = sorted(ctx.directories())

    dependencies: list[Dependency] = []
    entry_points: list[str] = []
    for scanner in SCANNERS:
        if scanner.matches(ctx):
            dependencies.extend(scanner.dependencies(ctx))
            entry_points.extend(scanner.entry_points(ctx))
    dependencies = _dedupe_dependencies(dependencies)
    entry_points = sorted(set(entry_points))

    return RepositoryInventory(
        path=str(ctx.root),
        fingerprint=fp,
        files=files,
        directories=directories,
        modules=modules,
        dependencies=dependencies,
        configs=configs,
        entry_points=entry_points,
        file_count=len(files),
        directory_count=len(directories),
        module_count=len(modules),
        dependency_count=len(dependencies),
        total_loc=total_loc,
    )


def _discover_modules(ctx: RepoContext) -> list[Module]:
    """A module is a directory that directly contains source files."""
    by_dir: dict[str, dict[str, int]] = {}
    for rel, _ in ctx.files():
        lang = CODE_EXTENSIONS.get(PurePosixPath(rel).suffix.lower())
        if not lang:
            continue
        parent = rel.rsplit("/", 1)[0] if "/" in rel else "."
        by_dir.setdefault(parent, {})
        by_dir[parent][lang] = by_dir[parent].get(lang, 0) + 1

    modules: list[Module] = []
    for path, langs in by_dir.items():
        dominant = max(langs, key=lambda k: langs[k])
        modules.append(Module(path=path, language=dominant, file_count=sum(langs.values())))
    modules.sort(key=lambda m: m.path)
    return modules


def _is_config(rel: str) -> bool:
    name = PurePosixPath(rel).name
    if name in CONFIG_FILENAMES:
        return True
    if rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml")):
        return True
    if "/" not in rel and PurePosixPath(rel).suffix in {".toml", ".cfg", ".ini"}:
        return True
    return False


def _dedupe_dependencies(deps: list[Dependency]) -> list[Dependency]:
    seen: set[tuple[str, str]] = set()
    unique: list[Dependency] = []
    for dep in deps:
        key = (dep.name, dep.source)
        if key in seen:
            continue
        seen.add(key)
        unique.append(dep)
    return unique
