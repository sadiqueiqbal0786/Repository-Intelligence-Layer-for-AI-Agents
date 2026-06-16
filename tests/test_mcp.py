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
        "get_module_info",
        "get_dependencies",
        "get_critical_files",
        "explain_module",
        "analyze_impact",
    }
