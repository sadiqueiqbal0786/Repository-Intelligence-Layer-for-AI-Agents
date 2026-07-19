"""Build-time coverage self-assessment (trust layer).

A persistent memory's worst failure is confident silence: the pubspec-not-found
bug under-counted imports and still reported files as "isolated, safe to change."
This module makes the graph grade itself so that failure is *loud* — an agent
(and a pre-ship check) can see how much of the repo actually resolved.

Everything here is a deterministic read over the finished inventory + graph; no
new parsing. ``connectivity`` — the share of graphed source files that have any
import edge — is the headline: near-zero on a real app means imports didn't
resolve, which is exactly the class of bug that used to ship silently.
"""

from __future__ import annotations

from repointel.models import (
    ArchitectureGraph,
    GraphCoverage,
    LanguageCoverage,
    RepositoryInventory,
)

# Below this share of connected files (on a repo big enough to judge), the graph
# is probably missing edges rather than genuinely describing isolated files.
_LOW_CONNECTIVITY = 0.5
_MIN_FILES_TO_JUDGE = 5


def assess_coverage(
    inventory: RepositoryInventory,
    graph: ArchitectureGraph,
    graphed_languages: set[str],
) -> GraphCoverage:
    """Grade how completely ``graph`` covers ``inventory``.

    ``graphed_languages`` is the set of languages a parser exists for; a language
    present in the inventory but absent here is reported as *inventory only* so an
    agent never assumes the dependency graph is complete for it.
    """
    # Per-language file counts from the fingerprint (source files only).
    lang_files = dict(inventory.fingerprint.languages)
    languages = [
        LanguageCoverage(language=lang, files=count, graphed=lang in graphed_languages)
        for lang, count in sorted(lang_files.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    ungraphed = [lc.language for lc in languages if not lc.graphed and lc.files]

    # Connectivity is measured only over files we actually try to graph — an
    # un-parsed Swift file being edgeless is expected, not a coverage failure.
    import_edges = [e for e in graph.edges if e.kind == "imports"]
    connected_ids = {e.source for e in import_edges} | {e.target for e in import_edges}
    source_files = 0
    connected = 0
    for node in graph.nodes:
        if node.kind != "file" or node.language not in graphed_languages:
            continue
        source_files += 1
        if node.id in connected_ids or f"file:{node.path}" in connected_ids:
            connected += 1
    isolated = source_files - connected
    connectivity = round(connected / source_files, 3) if source_files else 0.0

    warnings = _warnings(source_files, connectivity, len(import_edges), ungraphed)
    return GraphCoverage(
        confidence=_confidence(source_files, connectivity),
        source_files=source_files,
        connected_files=connected,
        isolated_files=isolated,
        connectivity=connectivity,
        import_edges=len(import_edges),
        languages=languages,
        ungraphed_languages=ungraphed,
        warnings=warnings,
    )


def _confidence(source_files: int, connectivity: float) -> str:
    if source_files < _MIN_FILES_TO_JUDGE:
        return "unknown"  # too little to grade honestly
    if connectivity >= 0.7:
        return "high"
    if connectivity >= _LOW_CONNECTIVITY:
        return "medium"
    return "low"


def _warnings(
    source_files: int, connectivity: float, import_edges: int, ungraphed: list[str]
) -> list[str]:
    warnings: list[str] = []
    if source_files >= _MIN_FILES_TO_JUDGE and connectivity < _LOW_CONNECTIVITY:
        pct = round(connectivity * 100)
        detail = (
            "no import edges at all" if import_edges == 0 else f"only {pct}% have any"
        )
        warnings.append(
            f"Low dependency connectivity: {detail} import edge across "
            f"{source_files} graphed source files. Imports may be unresolved — "
            "e.g. a package manifest that wasn't found. Treat dependents/"
            '"safe to change" verdicts with caution.'
        )
    if ungraphed:
        warnings.append(
            f"Inventory only (no dependency graph) for: {', '.join(ungraphed)}. "
            "Impact/consumer results do not account for these files."
        )
    return warnings


__all__ = ["assess_coverage"]
