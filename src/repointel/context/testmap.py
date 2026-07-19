"""Source → test mapping.

Before editing a file, an agent's top question is "which tests cover this, so I
know what to run?" — otherwise it runs the whole suite or greps. Two signals
answer it from memory: test files that **import** the source (an explicit
dependency edge in the graph) and test files that **match its name** by the
usual conventions (``foo.dart`` ↔ ``foo_test.dart``, ``foo.py`` ↔
``test_foo.py``). Both are reported with how they were found, so the caller can
judge confidence.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from repointel.graph.builder import file_id
from repointel.graph.traversal import GraphView
from repointel.models import ArchitectureGraph
from repointel.scanners.base import is_test_path


def tests_for(graph: ArchitectureGraph, target: str) -> dict:
    """Test files that cover ``target`` (a source file path or name)."""
    view = GraphView(graph)
    source = _resolve_source(graph, target)
    if source is None:
        return {"target": target, "found": False, "tests": []}

    by_import = {
        n.path
        for n in view.dependents(file_id(source))
        if n.path and is_test_path(n.path)
    }
    test_files = [
        n.path
        for n in graph.nodes
        if n.kind == "file" and n.path and is_test_path(n.path)
    ]
    by_name = {t for t in test_files if _name_matches(source, t)}

    tests = []
    for path in sorted(by_import | by_name):
        how = []
        if path in by_import:
            how.append("imports")
        if path in by_name:
            how.append("name")
        tests.append({"path": path, "matched_by": how})
    return {"target": source, "found": True, "tests": tests}


def _resolve_source(graph: ArchitectureGraph, target: str) -> str | None:
    """Resolve ``target`` to a concrete file path, preferring real source."""
    files = [n.path for n in graph.nodes if n.kind == "file" and n.path]
    if target in files:
        return target
    q = target.strip("/")
    matches = [
        p for p in files if PurePosixPath(p).name == q or p.endswith(f"/{q}")
    ]
    if not matches:
        return None
    matches.sort(key=lambda p: (is_test_path(p), p.count("/"), p))
    return matches[0]


def _name_matches(source: str, test: str) -> bool:
    """Whether ``test``'s filename is the conventional test for ``source``."""
    src_stem = PurePosixPath(source).stem
    test_stem = PurePosixPath(test).stem
    if not src_stem:
        return False
    return test_stem in (
        f"{src_stem}_test",
        f"test_{src_stem}",
        f"{src_stem}_spec",
        f"{src_stem}.test",
        f"{src_stem}.spec",
    )


__all__ = ["tests_for"]
