"""Tests for Phase 7 incremental intelligence."""

from __future__ import annotations

import os
from pathlib import Path

from repointel.context.incremental import update_memory
from repointel.context.memory import build_memory, persist_memory
from repointel.graph.builder import build_graph
from repointel.scanners import scan_repo
from repointel.storage.json import read_cache


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _bump_mtime(root: Path, rel: str) -> None:
    """Push a file's mtime forward so size-equal edits still register."""
    target = root / rel
    st = target.stat()
    os.utime(target, (st.st_atime + 10, st.st_mtime + 10))


_SERVICE_SRC = "from demo.models import User\n\n\ndef make():\n    return User()\n"


def _project(root: Path) -> None:
    _write(root, "pyproject.toml", '[project]\nname = "demo"\ndependencies = ["fastapi>=0.110"]\n')
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(root, "src/demo/service.py", _SERVICE_SRC)


def _seed(root: Path) -> None:
    """Build + persist full memory so a cache exists for later updates."""
    persist_memory(build_memory(root), root)


def test_update_without_cache_does_full_build(tmp_path: Path) -> None:
    _project(tmp_path)
    bundle, changes = update_memory(tmp_path)
    assert changes.full_rebuild is True
    assert bundle.repo.node_count > 0


def test_update_detects_no_changes(tmp_path: Path) -> None:
    _project(tmp_path)
    _seed(tmp_path)
    _, changes = update_memory(tmp_path)
    assert not changes.full_rebuild
    assert not changes.has_changes
    assert changes.changed_count == 0
    assert changes.unchanged > 0


def test_update_detects_modified_file(tmp_path: Path) -> None:
    _project(tmp_path)
    _seed(tmp_path)

    admin_src = "class User:\n    pass\n\n\nclass Admin(User):\n    pass\n"
    _write(tmp_path, "src/demo/models.py", admin_src)
    _bump_mtime(tmp_path, "src/demo/models.py")

    bundle, changes = update_memory(tmp_path)
    assert changes.modified == ["src/demo/models.py"]
    assert not changes.added and not changes.deleted
    # The new class is reflected in the graph (parse ran for the changed file).
    assert any(n.kind == "class" and n.name == "Admin" for n in bundle.graph.nodes)


def test_update_detects_added_and_deleted(tmp_path: Path) -> None:
    _project(tmp_path)
    _seed(tmp_path)

    _write(tmp_path, "src/demo/repo.py", "class Repo:\n    pass\n")
    (tmp_path / "src/demo/service.py").unlink()

    bundle, changes = update_memory(tmp_path)
    assert changes.added == ["src/demo/repo.py"]
    assert changes.deleted == ["src/demo/service.py"]
    paths = {n.path for n in bundle.graph.nodes if n.path}
    assert "src/demo/repo.py" in paths
    assert "src/demo/service.py" not in paths


def test_incremental_matches_full_build(tmp_path: Path) -> None:
    """Incremental output must be identical to a from-scratch build."""
    _project(tmp_path)
    _seed(tmp_path)

    team_src = "class User:\n    name: str\n\n\nclass Team:\n    pass\n"
    _write(tmp_path, "src/demo/models.py", team_src)
    _bump_mtime(tmp_path, "src/demo/models.py")

    incremental, _ = update_memory(tmp_path)
    full = build_memory(tmp_path)

    assert incremental.graph.node_count == full.graph.node_count
    assert incremental.graph.edge_count == full.graph.edge_count
    assert incremental.repo.total_loc == full.repo.total_loc
    assert incremental.modules.model_dump() == full.modules.model_dump()


def test_cache_reuse_preserves_loc_for_unchanged(tmp_path: Path) -> None:
    _project(tmp_path)
    _seed(tmp_path)
    cache = read_cache(tmp_path)
    assert cache is not None
    # Parsed IR is cached for the parseable source files.
    assert cache.files["src/demo/models.py"].parsed is not None
    assert cache.files["src/demo/models.py"].loc > 0


def test_parse_cache_reuse_is_correct_on_pure_edit(tmp_path: Path) -> None:
    """A pure edit (no add/delete) takes the parse-cache fast path yet stays
    consistent with a full graph build."""
    _project(tmp_path)
    _seed(tmp_path)

    edited_src = "from demo.models import User\n\n\ndef make():\n    u = User()\n    return u\n"
    _write(tmp_path, "src/demo/service.py", edited_src)
    _bump_mtime(tmp_path, "src/demo/service.py")

    bundle, changes = update_memory(tmp_path)
    assert changes.modified == ["src/demo/service.py"]

    inventory = scan_repo(tmp_path)
    full_graph = build_graph(tmp_path, inventory)
    assert bundle.graph.edge_count == full_graph.edge_count
