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
    # Mirror production (cli/commands/graph.py): scan_repo may resolve a nested
    # project root, so build from the SAME path it actually scanned.
    return build_graph(Path(inventory.path), inventory)


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


def test_dart_package_import_from_subfolder_pubspec(tmp_path: Path) -> None:
    """A Flutter app in a subfolder (``app/pubspec.yaml``) must still resolve
    ``package:<name>/…`` imports. Regression: the resolver only read a
    root-level pubspec, so every package import silently produced NO edge and
    the whole import graph collapsed for subfolder/monorepo layouts.

    A sibling package (``server/``) keeps the analysis at the repo root — the
    real monorepo case where the app is NOT the sole project — so paths keep
    their ``app/`` prefix, exactly like the MTD repo that surfaced this bug."""
    _write(tmp_path, "server/pyproject.toml", '[project]\nname = "server"\n')
    _write(tmp_path, "server/main.py", "x = 1\n")
    _write(tmp_path, "app/pubspec.yaml", "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n")
    _write(tmp_path, "app/lib/models/thing.dart", "class Thing {}\n")
    # Imported from FAR AWAY via a package: import (the case relative-import
    # resolution can't cover).
    _write(
        tmp_path,
        "app/lib/src/feature/widget.dart",
        "import 'package:app/models/thing.dart';\n\nclass Widget {}\n",
    )
    g = _graph(tmp_path)
    view = GraphView(g)

    deps = view.dependencies(file_id("app/lib/src/feature/widget.dart"))
    assert file_id("app/lib/models/thing.dart") in {n.id for n in deps}
    # And the reverse edge exists — the model has a real consumer (not "isolated").
    consumers = view.dependents(file_id("app/lib/models/thing.dart"))
    assert file_id("app/lib/src/feature/widget.dart") in {n.id for n in consumers}


def test_dart_export_barrel_creates_dependency_edge(tmp_path: Path) -> None:
    """A barrel file that ``export``s another must depend on it, so a consumer
    importing the barrel transitively reaches the underlying file. Regression:
    only ``import`` was parsed, so a file reached solely via a barrel looked
    like it had no dependents (falsely 'safe to change')."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(tmp_path, "lib/models/goal.dart", "class Goal {}\n")
    _write(tmp_path, "lib/models.dart", "export 'models/goal.dart';\n")  # barrel
    _write(
        tmp_path,
        "lib/feature.dart",
        "import 'package:shop/models.dart';\n\nclass Feature {}\n",
    )
    g = _graph(tmp_path)
    view = GraphView(g)

    # Barrel → goal (the export edge).
    assert file_id("lib/models/goal.dart") in {
        n.id for n in view.dependencies(file_id("lib/models.dart"))
    }
    # And goal's dependents include the barrel (not 'isolated').
    assert file_id("lib/models.dart") in {
        n.id for n in view.dependents(file_id("lib/models/goal.dart"))
    }


def test_generated_dart_files_are_not_graph_nodes(tmp_path: Path) -> None:
    """`*.g.dart` / `*.freezed.dart` are machine-generated: they must not become
    graph nodes or contribute classes (they otherwise swamp a freezed-heavy
    module's class/LOC counts)."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(
        tmp_path,
        "lib/user.dart",
        "part 'user.freezed.dart';\npart 'user.g.dart';\n\nclass User {}\n",
    )
    _write(tmp_path, "lib/user.freezed.dart", "class _$UserImpl {}\nmixin _$User {}\n")
    _write(tmp_path, "lib/user.g.dart", "class _$UserJson {}\n")
    g = _graph(tmp_path)
    ids = {n.id for n in g.nodes}

    assert file_id("lib/user.dart") in ids
    assert file_id("lib/user.freezed.dart") not in ids
    assert file_id("lib/user.g.dart") not in ids
    # The generated mixin/impl classes must not be counted.
    class_names = {n.name for n in g.nodes if n.kind == "class"}
    assert "User" in class_names
    assert not any(c.startswith("_$") for c in class_names)


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
