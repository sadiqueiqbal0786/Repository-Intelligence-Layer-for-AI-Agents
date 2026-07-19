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
from pathlib import Path, PurePosixPath

from repointel.models import (
    ArchitectureSummary,
    Contributor,
    Conventions,
    Decision,
    DocBrief,
    Knowledge,
    Note,
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
    """Assemble the knowledge layer, preserving written-back decisions + notes."""
    decisions = discover_decisions(root)
    notes: list[Note] = []
    if previous is not None:
        manual = [d for d in previous.decisions if d.source == "manual"]
        decisions = _dedupe_decisions([*decisions, *manual])
        notes = list(previous.notes)  # agent write-backs survive rebuilds
    return Knowledge(
        decisions=decisions,
        patterns=infer_patterns(conventions, architecture),
        history=project_history(root),
        docs=discover_docs(root),
        notes=notes,
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


def record_note(
    root: Path, text: str, *, scope: str | None = None, source: str = "agent"
) -> Note:
    """Write an agent/human discovery back into durable memory and persist it.

    This is the feedback loop: what one agent learns ("this endpoint must write
    to the default DB, not the named one") is inherited by the next, instead of
    every session re-discovering it. Notes survive rebuilds.
    """
    root = Path(root)
    knowledge = load_knowledge(root) or Knowledge()

    existing = {n.id for n in knowledge.notes}
    base = _slugify(text)[:40] or "note"
    note_id, suffix = base, 2
    while note_id in existing:
        note_id, suffix = f"{base}-{suffix}", suffix + 1

    note = Note(
        id=note_id,
        text=text,
        scope=scope,
        created=_date.today().isoformat(),
        source=source,
    )
    knowledge.notes.append(note)
    write_knowledge(knowledge, root)
    return note


def notes_for_scope(knowledge: Knowledge, scope: str) -> list[Note]:
    """Notes attached to ``scope`` or one of its parent paths (path-prefix match)."""
    matched: list[Note] = []
    for note in knowledge.notes:
        if note.scope and (scope == note.scope or scope.startswith(f"{note.scope}/")):
            matched.append(note)
    return matched


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


# ---- human docs (the "why") --------------------------------------------------

# Doc files that carry project rationale, in priority order. The graph can't
# derive intent — it lives in these hand-written files, so they belong in memory.
_DOC_CANDIDATES: tuple[str, ...] = (
    "README.md",
    "README.rst",
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "docs/README.md",
)
_DOC_LIMIT = 6
_SUMMARY_CHARS = 600
_HEADING_LIMIT = 20

_MD_HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*#*$", re.MULTILINE)


def discover_docs(root: Path) -> list[DocBrief]:
    """Ingest the human-written docs that hold the project's rationale.

    Each is distilled to a title, an opening-paragraph summary and its section
    headings — enough for an agent to know what's there and jump to it, without
    copying whole files into memory.
    """
    root = Path(root)
    briefs: list[DocBrief] = []
    for rel in _DOC_CANDIDATES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        brief = _summarize_doc(text, rel)
        if brief is not None:
            briefs.append(brief)
        if len(briefs) >= _DOC_LIMIT:
            break
    return briefs


def _summarize_doc(text: str, rel: str) -> DocBrief | None:
    if not text.strip():
        return None
    headings = [h.strip() for h in _MD_HEADING_RE.findall(text)]
    title = headings[0] if headings else PurePosixPath(rel).stem
    summary = _first_paragraph(text)
    return DocBrief(
        source=rel,
        title=title,
        summary=summary,
        headings=headings[1 : _HEADING_LIMIT + 1],  # drop the title heading
    )


def _first_paragraph(text: str) -> str | None:
    """The first real prose paragraph — skipping headings, badges and blank lines."""
    paragraph: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if paragraph:
                break
            continue
        if line.startswith(("#", "!", "<", "[!", "---", "===", "```")):
            continue  # heading, badge/image, HTML, admonition, rule, fence
        paragraph.append(line)
    if not paragraph:
        return None
    summary = " ".join(paragraph)
    return summary[:_SUMMARY_CHARS].rstrip() + ("…" if len(summary) > _SUMMARY_CHARS else "")


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


def file_churn(root: Path, max_commits: int = 1000) -> dict[str, int]:
    """Map each file to how many of the last ``max_commits`` commits touched it.

    Churn is the coupling/instability signal the import graph can't see: a file
    edited in many commits is where change concentrates. Combined with import
    in-degree it yields real risk hotspots (a heavily-imported file that also
    churns a lot), better than in-degree alone. Paths are ``--relative`` to
    ``root`` so a nested project (``app/``) reports its own files. Empty outside
    a git work tree.
    """
    out = _git(
        Path(root), "log", f"-n{max_commits}", "--relative", "--name-only", "--format="
    )
    if not out:
        return {}
    churn: dict[str, int] = {}
    for line in out.splitlines():
        path = line.strip()
        if path:
            churn[path] = churn.get(path, 0) + 1
    return churn


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
    "discover_docs",
    "file_churn",
    "head_commit",
    "infer_patterns",
    "load_knowledge",
    "notes_for_scope",
    "project_history",
    "record_decision",
    "record_note",
]
