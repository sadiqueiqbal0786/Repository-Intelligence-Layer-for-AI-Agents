"""Tests for the Phase 5 MCP tools and server."""

from __future__ import annotations

import asyncio
from pathlib import Path

from repointel.mcp import tools
from repointel.mcp.server import build_server
from repointel.storage.json import repository_path


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _project(root: Path) -> None:
    _write(
        root,
        "pyproject.toml",
        '[project]\nname = "demo"\ndependencies = ["fastapi>=0.110"]\n',
    )
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(
        root,
        "src/demo/service.py",
        "from demo.models import User\n\n\ndef make():\n    return User()\n",
    )
    _write(
        root,
        "src/demo/main.py",
        "from demo.models import User\n\n\ndef run():\n    return User\n",
    )


def test_ensure_memory_builds_on_first_call(tmp_path: Path) -> None:
    _project(tmp_path)
    assert not repository_path(tmp_path).exists()
    tools.get_project_summary(tmp_path)
    # Memory was built and persisted as a side effect.
    assert repository_path(tmp_path).exists()


def test_project_summary(tmp_path: Path) -> None:
    _project(tmp_path)
    summary = tools.get_project_summary(tmp_path)
    assert summary["name"] == tmp_path.name
    assert summary["fingerprint"]["framework"] == "FastAPI"
    assert "conventions" in summary
    assert summary["conventions"]["source_layout"] == "src"


def test_conventions(tmp_path: Path) -> None:
    _project(tmp_path)
    conv = tools.get_conventions(tmp_path)
    assert conv["source_layout"] == "src"
    assert conv["dependency_injection"] == "FastAPI"
    assert conv["naming"]["classes"] == "PascalCase"
    assert conv["naming"]["functions"] == "snake_case"


def test_architecture(tmp_path: Path) -> None:
    _project(tmp_path)
    arch = tools.get_architecture(tmp_path)
    assert "Python" in arch["languages"]
    assert "src/demo/models.py" in arch["key_files"]


def test_module_info_list_and_lookup(tmp_path: Path) -> None:
    _project(tmp_path)
    listing = tools.get_module_info(tmp_path)
    paths = {m["path"] for m in listing["modules"]}
    assert "src/demo" in paths

    detail = tools.get_module_info(tmp_path, "src/demo")
    assert detail["path"] == "src/demo"
    assert detail["classes"] == 1

    # Lookup by basename also works.
    by_name = tools.get_module_info(tmp_path, "demo")
    assert by_name["path"] == "src/demo"


def test_module_info_not_found(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.get_module_info(tmp_path, "does_not_exist")
    assert "error" in result
    assert "available" in result


def test_dependencies(tmp_path: Path) -> None:
    _project(tmp_path)
    deps = tools.get_dependencies(tmp_path)
    assert deps["count"] >= 1
    assert any(d["name"] == "fastapi" for d in deps["dependencies"])


def test_get_context(tmp_path: Path) -> None:
    _project(tmp_path)
    pack = tools.get_context(tmp_path)
    assert pack["name"] == tmp_path.name
    assert pack["framework"] == "FastAPI"
    assert pack["file_count"] >= 1
    assert "fastapi" in pack["top_dependencies"]


def test_get_knowledge(tmp_path: Path) -> None:
    _project(tmp_path)
    knowledge = tools.get_knowledge(tmp_path)
    assert "decisions" in knowledge
    assert "patterns" in knowledge
    assert "history" in knowledge
    # Patterns are inferred from conventions/architecture even for a tiny project.
    assert isinstance(knowledge["patterns"], list)


def test_explain_module(tmp_path: Path) -> None:
    _project(tmp_path)
    exp = tools.explain_module(tmp_path, "demo")
    assert exp["module"] == "src/demo"
    assert "User" in exp["key_classes"]
    assert exp["risk_level"] in {"low", "medium", "high"}


def test_explain_module_not_found(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.explain_module(tmp_path, "nope")
    assert "error" in result
    assert "available" in result


def test_analyze_impact(tmp_path: Path) -> None:
    _project(tmp_path)
    report = tools.analyze_impact(tmp_path, "models.py")
    assert report["file"] == "src/demo/models.py"
    # service.py and main.py both import models.py.
    assert report["affected_file_count"] == 2
    assert "src/demo/service.py" in report["affected_files"]
    assert report["risk_level"] in {"low", "medium", "high"}


def test_analyze_impact_not_found(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.analyze_impact(tmp_path, "ghost.py")
    assert "error" in result
    assert "candidates" in result


def test_critical_files(tmp_path: Path) -> None:
    _project(tmp_path)
    critical = tools.get_critical_files(tmp_path)
    top = critical["critical_files"][0]
    # models.py is imported by both service.py and main.py.
    assert top["path"] == "src/demo/models.py"
    assert top["imported_by"] == 2


def test_critical_files_excludes_test_infra(tmp_path: Path) -> None:
    """A heavily-imported test helper must not crowd out the real core file."""
    _project(tmp_path)
    # A test helper imported by two test files — high in-degree, but test infra.
    _write(tmp_path, "tests/fakes.py", "class Fake:\n    pass\n")
    _write(tmp_path, "tests/test_a.py", "from tests.fakes import Fake\n")
    _write(tmp_path, "tests/test_b.py", "from tests.fakes import Fake\n")
    critical = tools.get_critical_files(tmp_path)
    paths = [c["path"] for c in critical["critical_files"]]
    assert "src/demo/models.py" in paths  # real core file is visible
    assert all("test" not in p.split("/") for p in paths)  # no test dirs
    assert not any(p.endswith("fakes.py") for p in paths)
    assert critical["test_files_excluded"] >= 1


def test_hotspots_without_git_reports_unavailable(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.get_hotspots(tmp_path)
    assert result["available"] is False
    assert result["hotspots"] == []


def test_record_note_persists_and_surfaces_in_explain(tmp_path: Path) -> None:
    _project(tmp_path)
    out = tools.record_note(
        tmp_path,
        "models.py must stay import-free of the service layer",
        scope="src/demo",
    )
    assert out["recorded"] is True

    # Survives a rebuild and is exposed by get_knowledge.
    from repointel.context.memory import build_memory, persist_memory

    persist_memory(build_memory(tmp_path), tmp_path)
    knowledge = tools.get_knowledge(tmp_path)
    assert any("import-free" in n["text"] for n in knowledge["notes"])

    # Scoped note is attached to the module explanation.
    explanation = tools.explain_module(tmp_path, "demo")
    assert "notes" in explanation
    assert any("import-free" in n["text"] for n in explanation["notes"])


def test_get_feature_aggregates_subtree(tmp_path: Path) -> None:
    """A feature spanning several dirs is reported as one aggregate view."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(tmp_path, "lib/auth/data/auth_repo.dart", "class AuthRepo {}\n")
    _write(tmp_path, "lib/auth/bloc/auth_bloc.dart", "class AuthBloc {}\n")
    _write(tmp_path, "lib/auth/ui/login_page.dart", "class LoginPage {}\n")
    _write(tmp_path, "lib/home/home_page.dart", "class HomePage {}\n")
    feat = tools.get_feature(tmp_path, "auth")
    assert feat["found"] is True
    assert feat["root"] == "lib/auth"
    assert set(feat["modules"]) == {"lib/auth/data", "lib/auth/bloc", "lib/auth/ui"}
    assert feat["file_count"] == 3
    assert feat["classes"] == 3
    assert "lib/home" not in feat["modules"]


def test_find_symbol_locates_definition_and_callers(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.find_symbol(tmp_path, "make")
    assert result["found"] is True
    defn = result["definitions"][0]
    assert defn["path"] == "src/demo/service.py"
    assert defn["kind"] == "function"
    assert defn["line"]  # a real line number


def test_find_symbol_unknown(tmp_path: Path) -> None:
    _project(tmp_path)
    result = tools.find_symbol(tmp_path, "does_not_exist")
    assert result["found"] is False
    assert result["definitions"] == []


def test_what_tests_maps_source_to_tests(tmp_path: Path) -> None:
    _project(tmp_path)
    # A test that imports the source, plus a name-convention test file.
    _write(
        tmp_path,
        "tests/test_models.py",
        "from demo.models import User\n\n\ndef test_user():\n    assert User\n",
    )
    result = tools.what_tests(tmp_path, "models.py")
    assert result["found"] is True
    paths = {t["path"] for t in result["tests"]}
    assert "tests/test_models.py" in paths
    match = next(t for t in result["tests"] if t["path"] == "tests/test_models.py")
    assert "imports" in match["matched_by"] or "name" in match["matched_by"]


def test_get_health(tmp_path: Path) -> None:
    _project(tmp_path)
    health = tools.get_health(tmp_path)
    assert health["confidence"] in {"high", "medium", "low", "unknown"}
    assert "warnings" in health
    assert "languages" in health


def test_server_registers_all_tools(tmp_path: Path) -> None:
    _project(tmp_path)
    server = build_server(tmp_path)
    registered = {t.name for t in asyncio.run(server.list_tools())}
    assert registered == {
        "get_context",
        "get_project_summary",
        "get_architecture",
        "get_conventions",
        "get_knowledge",
        "get_health",
        "get_hotspots",
        "get_feature",
        "get_module_info",
        "get_dependencies",
        "get_critical_files",
        "find_symbol",
        "what_tests",
        "record_note",
        "explain_module",
        "analyze_impact",
    }
