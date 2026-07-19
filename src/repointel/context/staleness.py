"""Live staleness check — does the persisted memory still describe HEAD?

"Build once, reuse forever" only holds if the memory knows when it has drifted.
The build stamps the git commit it ran against (``RepoSummary.built_at_commit``);
this module compares that stamp to the current working tree at *read* time, so an
agent is told "memory is N files behind — refresh it" instead of trusting a
snapshot of a codebase that has moved on.

Read-only: it reports drift, it never rebuilds (that is ``repointel update``).
"""

from __future__ import annotations

from pathlib import Path

from repointel.context.knowledge import changed_files_since, head_commit


def assess_staleness(root: Path, built_at_commit: str | None) -> dict:
    """Compare the memory's build commit to the current HEAD/working tree.

    Returns a JSON-friendly dict: ``is_git``, ``stale``, ``built_at_commit``,
    ``current_commit``, ``changed_files``, and a human-readable ``message``
    (``None`` when fresh or not applicable).
    """
    current = head_commit(root)
    result = {
        "is_git": current is not None,
        "stale": False,
        "built_at_commit": built_at_commit,
        "current_commit": current,
        "changed_files": 0,
        "message": None,
    }
    if current is None:
        return result  # not a git repo — nothing to compare against
    if not built_at_commit:
        result["message"] = (
            "Memory has no build-commit stamp (built by an older version). "
            "Rebuild to enable staleness detection."
        )
        return result

    changed = changed_files_since(root, built_at_commit)
    if changed is None:
        # The stamped commit is unknown here (e.g. shallow clone / rebased).
        if built_at_commit != current:
            result["stale"] = True
            result["message"] = (
                f"Memory was built at {built_at_commit[:8]} but HEAD is "
                f"{current[:8]} — run `repointel update` to refresh."
            )
        return result

    result["changed_files"] = changed
    if changed > 0:
        result["stale"] = True
        result["message"] = (
            f"Memory is stale: built at {built_at_commit[:8]}, {changed} file(s) "
            "changed since — run `repointel update` to refresh."
        )
    return result


__all__ = ["assess_staleness"]
