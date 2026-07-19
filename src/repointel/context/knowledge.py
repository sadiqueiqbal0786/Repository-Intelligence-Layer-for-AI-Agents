"""Knowledge layer (Phase 11).

Turns structure into *understanding* and gives the repository long-term memory:

- **decisions** — architecture decisions, discovered from ADR markdown files and
  augmented by ones recorded with :func:`record_decision` (which persist across
  rebuilds);
- **patterns** — the practices the codebase follows, inferred from the Phase 6
  conventions and the architecture summary;
- **history** — project evolution, derived from git.

Derived parts are regenerated each build; manually recorded decisions are merged
back in so they are never lost.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date as _date
from pathlib import Path

from repointel.models import (
    ArchitectureSummary,
    Contributor,
    Conventions,
    Decision,
    Knowledge,
    Pattern,
    ProjectHistory,
)
from repointel.storage.json import read_knowledge, write_knowledge

_ADR_DIRS = (
    "docs/adr",
    "docs/adrs",
    "docs/decisions",
    "docs/architecture/decisions",
    "doc/adr",
    "adr",
    "architecture/decisions",
)

# Human-readable descriptions for the structural patterns Phase 6 detects.
_PATTERN_DESC = {
    "repository_pattern": "Data access is isolated behind repository types.",
    "service_layer": "Business logic lives in a dedicated service layer.",
    "controller_layer": "Requests are handled by controller types.",
    "use_case_pattern": "Application logic is organized as use cases.",
    "feature_modules": "Code is organized into feature/module folders.",
    "dependency_injection": "Dependencies are wired via dependency injection.",
}

_HEADING_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)
_TITLE_PREFIX_RE = re.compile(r"^(?:adr[\s\-:]*)?\d+[.\-:)\s]+", re.IGNORECASE)


# ---- assembly + persistence --------------------------------------------------


def build_knowledge(
    root: Path,
    conventions: Conventions | None = None,
    architecture: ArchitectureSummary | None = None,
    previous: Knowledge | None = None,
) -> Knowledge:
    """Assemble the knowledge layer, preserving manually recorded decisions."""
    decisions = discover_decisions(root)
    if previous is not None:
        manual = [d for d in previous.decisions if d.source == "manual"]
        decisions = _dedupe_decisions([*decisions, *manual])
    return Knowledge(
        decisions=decisions,
        patterns=infer_patterns(conventions, architecture),
        history=project_history(root),
    )


def load_knowledge(root: Path) -> Knowledge | None:
    return read_knowledge(Path(root))


def record_decision(
    root: Path,
    title: str,
    *,
    status: str = "accepted",
    rationale: str | None = None,
    context: str | None = None,
    date: str | None = None,
) -> Decision:
    """Record a decision into the durable knowledge store and persist it."""
    root = Path(root)
    knowledge = load_knowledge(root) or Knowledge()

    base = _slugify(title) or "decision"
    existing = {d.id for d in knowledge.decisions}
    decision_id, suffix = base, 2
    while decision_id in existing:
        decision_id, suffix = f"{base}-{suffix}", suffix + 1

    decision = Decision(
        id=decision_id,
        title=title,
        status=status,
        date=date or _date.today().isoformat(),
        context=context,
        rationale=rationale,
        source="manual",
    )
    knowledge.decisions.append(decision)
    write_knowledge(knowledge, root)
    return decision


# ---- decisions ---------------------------------------------------------------


def discover_decisions(root: Path) -> list[Decision]:
    """Find and parse ADR markdown files under the conventional locations."""
    root = Path(root)
    decisions: list[Decision] = []
    for rel_dir in _ADR_DIRS:
        directory = root / rel_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name.lower() in {"readme.md", "index.md", "template.md"}:
                continue
            decision = _parse_adr(path, f"{rel_dir}/{path.name}")
            if decision is not None:
                decisions.append(decision)
    return _dedupe_decisions(decisions)


def _parse_adr(path: Path, rel: str) -> Decision | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    heading = _HEADING_RE.search(text)
    title = _TITLE_PREFIX_RE.sub("", heading.group(1).strip()) if heading else path.stem
    status = _first_line(_section(text, "Status"))
    context = _section(text, "Context") or None
    rationale = _section(text, "Decision") or None
    return Decision(
        id=path.stem,
        title=title or path.stem,
        status=status,
        date=_section_value(text, "Date"),
        context=context,
        rationale=rationale,
        source=f"adr:{rel}",
    )


def _section(text: str, name: str) -> str | None:
    """The body under a ``## <name>`` heading, up to the next ``##`` heading."""
    pattern = re.compile(
        rf"^##+\s+{re.escape(name)}\s*$(.*?)(?=^##+\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    body = match.group(1).strip()
    return body or None


def _section_value(text: str, name: str) -> str | None:
    """A ``Name: value`` inline field, if present."""
    match = re.search(rf"^{re.escape(name)}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def _dedupe_decisions(decisions: list[Decision]) -> list[Decision]:
    seen: set[str] = set()
    unique: list[Decision] = []
    for decision in decisions:
        if decision.id in seen:
            continue
        seen.add(decision.id)
        unique.append(decision)
    return unique


# ---- patterns ----------------------------------------------------------------


def infer_patterns(
    conventions: Conventions | None, architecture: ArchitectureSummary | None
) -> list[Pattern]:
    patterns: list[Pattern] = []
    if architecture is not None and architecture.style:
        patterns.append(
            Pattern(
                name=architecture.style,
                kind="architecture",
                description=f"The codebase follows a {architecture.style} architecture.",
                evidence="directory layout",
            )
        )
    if conventions is None:
        return patterns

    if conventions.dependency_injection:
        patterns.append(
            Pattern(
                name=conventions.dependency_injection,
                kind="dependency",
                description=f"Dependencies are wired via {conventions.dependency_injection}.",
                evidence="declared dependencies",
            )
        )
    for name in conventions.patterns:
        if name == "dependency_injection":
            continue  # already represented above
        patterns.append(
            Pattern(
                name=name,
                kind="structural",
                description=_PATTERN_DESC.get(name, name.replace("_", " ")),
                evidence="directory and file names",
            )
        )
    naming = (("classes", conventions.naming.classes), ("functions", conventions.naming.functions))
    for label, style in naming:
        if style:
            patterns.append(
                Pattern(
                    name=f"{style} {label}",
                    kind="convention",
                    description=f"{label.capitalize()} are named in {style}.",
                    evidence="graph symbols",
                )
            )
    if conventions.testing.framework:
        patterns.append(
            Pattern(
                name=conventions.testing.framework,
                kind="testing",
                description=f"Tests use {conventions.testing.framework}.",
                evidence="dependencies and test files",
            )
        )
    return patterns


# ---- history -----------------------------------------------------------------


def project_history(root: Path) -> ProjectHistory:
    """Derive project evolution from git; empty when ``root`` is not inside a git
    work tree.

    Uses ``git rev-parse`` rather than checking for a ``.git`` directory, so it
    also works when ``root`` is a *subdirectory* of the repo (a monorepo package,
    e.g. ``app/`` next to the repo-root ``.git``) and degrades gracefully when the
    ``git`` binary is absent.
    """
    root = Path(root)
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.strip() != "true":
        return ProjectHistory(is_git=False)

    total = _git(root, "rev-list", "--count", "HEAD")
    if total is None:
        return ProjectHistory(is_git=False)

    history = ProjectHistory(is_git=True, total_commits=_to_int(total))
    if last := _git(root, "log", "-1", "--format=%aI"):
        history.last_commit_date = last.strip() or None
    history.first_commit_date = _first_commit_date(root)
    history.top_contributors, history.contributor_count = _contributors(root)
    if log := _git(root, "log", "-n", "20", "--format=%s"):
        history.recent_commits = [line for line in log.splitlines() if line.strip()]
    return history


def head_commit(root: Path) -> str | None:
    """The current ``HEAD`` commit SHA, or ``None`` outside a git work tree."""
    out = _git(Path(root), "rev-parse", "HEAD")
    return out.strip() if out else None


def changed_files_since(root: Path, commit: str) -> int | None:
    """How many tracked files differ between ``commit`` and the working tree
    (committed + uncommitted). ``None`` if the diff can't be computed."""
    out = _git(Path(root), "diff", "--name-only", commit)
    if out is None:
        return None
    return len([line for line in out.splitlines() if line.strip()])


def _first_commit_date(root: Path) -> str | None:
    roots = _git(root, "rev-list", "--max-parents=0", "HEAD")
    if not roots or not roots.split():
        return None
    shown = _git(root, "show", "-s", "--format=%aI", roots.split()[0])
    return shown.strip() if shown else None


def _contributors(root: Path) -> tuple[list[Contributor], int]:
    out = _git(root, "shortlog", "-sn", "HEAD")
    if not out:
        return [], 0
    contributors: list[Contributor] = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        count, _, name = stripped.partition("\t")
        if name:
            contributors.append(Contributor(name=name.strip(), commits=_to_int(count)))
    return contributors[:5], len(contributors)


def _git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _to_int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return 0


def _slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


__all__ = [
    "build_knowledge",
    "changed_files_since",
    "discover_decisions",
    "head_commit",
    "infer_patterns",
    "load_knowledge",
    "project_history",
    "record_decision",
]
