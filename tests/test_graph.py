"""Tests for Phase 3 architecture graph building + traversal."""

from __future__ import annotations

from pathlib import Path

from repointel.graph.builder import (
    build_graph,
    class_id,
    file_id,
    function_id,
    module_id,
)
from repointel.graph.traversal import GraphView
from repointel.scanners import scan_repo
from repointel.storage.json import read_graph, write_graph


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _python_project(root: Path) -> None:
    _write(root, "pyproject.toml", '[project]\nname = "demo"\n')
    _write(root, "src/demo/__init__.py", "")
    _write(
        root,
        "src/demo/models.py",
        "class Base:\n    pass\n\n\nclass User(Base):\n    def name(self):\n        return 1\n",
    )
    _write(
        root,
        "src/demo/service.py",
        "from demo.models import User\n\n\ndef make_user():\n    return User()\n",
    )
    _write(
        root,
        "src/demo/main.py",
        "from demo.service import make_user\n\n\ndef run():\n    return make_user()\n",
    )


def _graph(root: Path):
    inventory = scan_repo(root)
    return build_graph(root, inventory)


def test_nodes_created(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    ids = {n.id for n in g.nodes}

    assert module_id("src/demo") in ids
    assert file_id("src/demo/models.py") in ids
    assert class_id("src/demo/models.py", "User") in ids
    assert function_id("src/demo/service.py", "make_user") in ids
    # Method node qualified by class name.
    assert function_id("src/demo/models.py", "User.name") in ids
    assert g.node_kinds["class"] == 2


def test_contains_edges(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    view = GraphView(g)

    files = view.neighbors(module_id("src/demo"), kind="contains")
    assert file_id("src/demo/models.py") in {n.id for n in files}

    classes = view.neighbors(file_id("src/demo/models.py"), kind="contains")
    assert class_id("src/demo/models.py", "User") in {n.id for n in classes}


def test_import_edges_resolved(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    view = GraphView(g)

    deps = view.dependencies(file_id("src/demo/main.py"))
    assert file_id("src/demo/service.py") in {n.id for n in deps}

    dependents = view.dependents(file_id("src/demo/models.py"))
    assert file_id("src/demo/service.py") in {n.id for n in dependents}


def test_extends_edge(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    extends = [e for e in g.edges if e.kind == "extends"]
    assert any(
        e.source == class_id("src/demo/models.py", "User")
        and e.target == class_id("src/demo/models.py", "Base")
        for e in extends
    )


def test_calls_edge(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    calls = [e for e in g.edges if e.kind == "calls"]
    # run() calls make_user() — a uniquely named top-level function.
    assert any(
        e.source == function_id("src/demo/main.py", "run")
        and e.target == function_id("src/demo/service.py", "make_user")
        for e in calls
    )


def test_transitive_dependents(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    view = GraphView(g)
    # models <- service <- main
    reachable = view.transitive_dependents(file_id("src/demo/models.py"))
    assert file_id("src/demo/service.py") in reachable
    assert file_id("src/demo/main.py") in reachable


def test_dart_inheritance_and_imports(tmp_path: Path) -> None:
    _write(tmp_path, "pubspec.yaml", "name: shop\ndependencies:\n  flutter:\n    sdk: flutter\n")
    _write(tmp_path, "lib/base.dart", "abstract class Repo {}\nclass Logger {}\n")
    _write(
        tmp_path,
        "lib/user_repo.dart",
        "import 'package:shop/base.dart';\n\nclass UserRepo extends Repo implements Logger {}\n",
    )
    g = _graph(tmp_path)
    view = GraphView(g)

    deps = view.dependencies(file_id("lib/user_repo.dart"))
    assert file_id("lib/base.dart") in {n.id for n in deps}

    kinds = {(e.kind) for e in g.edges if e.source == class_id("lib/user_repo.dart", "UserRepo")}
    assert "extends" in kinds
    assert "implements" in kinds


def test_graph_storage_round_trip(tmp_path: Path) -> None:
    _python_project(tmp_path)
    g = _graph(tmp_path)
    write_graph(g, tmp_path)

    loaded = read_graph(tmp_path)
    assert loaded is not None
    assert loaded.node_count == g.node_count
    assert loaded.edge_count == g.edge_count


def test_syntax_error_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    _write(tmp_path, "broken.py", "def (:: this is not python\n")
    _write(tmp_path, "ok.py", "def fine():\n    return 1\n")

    g = _graph(tmp_path)
    ids = {n.id for n in g.nodes}
    assert function_id("ok.py", "fine") in ids
    # Broken file still gets a file node, just no parsed children.
    assert file_id("broken.py") in ids
