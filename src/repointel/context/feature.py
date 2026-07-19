"""Feature-level view — a feature is a subtree, not a single directory.

``get_module_info`` treats every directory that holds source as its own module,
so a feature like ``calendars`` that spans ``calendars/bloc``,
``calendars/data`` and ``calendars/presentation`` reads as three unrelated
modules. Agents think in features ("where does F live, what does it touch?"), so
this aggregates the whole subtree rooted at the named segment into one view:
combined size, its sub-modules, what it depends on *outside* itself, and who
depends on *it*.
"""

from __future__ import annotations

from repointel.models import ModuleSummary
from repointel.scanners.base import is_test_path


def describe_feature(modules: list[ModuleSummary], name: str) -> dict | None:
    """Aggregate every module under the ``name`` subtree into one feature view.

    Returns ``None`` when no module path contains ``name`` as a segment.
    """
    q = name.strip("/")
    seg = [m for m in modules if q in m.path.split("/")]
    if not seg:
        return None
    # Root the feature at the shallowest real-source occurrence of the segment.
    seg.sort(key=lambda m: (is_test_path(m.path), m.path.count("/"), m.path))
    root = _feature_root(seg[0].path, q)

    members = [m for m in modules if m.path == root or m.path.startswith(f"{root}/")]
    member_paths = {m.path for m in members}

    languages: dict[str, int] = {}
    for m in members:
        if m.language:
            languages[m.language] = languages.get(m.language, 0) + m.file_count

    external_deps = sorted(
        {imp for m in members for imp in m.imports if imp not in member_paths}
    )
    consumers = sorted(
        m.path
        for m in modules
        if m.path not in member_paths and any(p in m.imports for p in member_paths)
    )

    prod_members = [m for m in members if not is_test_path(m.path)]
    return {
        "feature": q,
        "root": root,
        "found": True,
        "modules": sorted(member_paths),
        "test_modules": sorted(m.path for m in members if is_test_path(m.path)),
        "file_count": sum(m.file_count for m in prod_members),
        "loc": sum(m.loc for m in prod_members),
        "classes": sum(m.classes for m in prod_members),
        "functions": sum(m.functions for m in prod_members),
        "languages": languages,
        "depends_on": external_deps,
        "consumers": consumers,
    }


def _feature_root(path: str, segment: str) -> str:
    parts = path.split("/")
    idx = parts.index(segment)
    return "/".join(parts[: idx + 1])


__all__ = ["describe_feature"]
