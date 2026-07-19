"""MCP server (Phase 5) — exposes repository intelligence to AI agents.

Wraps the pure functions in :mod:`repointel.mcp.tools` as MCP tools. The ``mcp``
SDK is imported lazily inside :func:`build_server` so importing this module (and
the rest of the package) never hard-requires the SDK.

Tools: ``get_context``, ``get_project_summary``, ``get_architecture``,
``get_conventions``, ``get_knowledge``, ``get_health``, ``get_module_info``,
``get_dependencies``, ``get_critical_files``, ``get_hotspots``,
``explain_module``, ``analyze_impact``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from repointel.mcp import tools

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def build_server(root: Path) -> FastMCP:
    """Create a FastMCP server whose tools serve memory for ``root``."""
    from mcp.server.fastmcp import FastMCP

    from repointel.scanners import resolve_project_root

    # Resolve a nested project root once (e.g. app/) so every tool reads and
    # writes the same .repointel/ location.
    root = resolve_project_root(Path(root).resolve())
    server = FastMCP("repointel")

    @server.tool()
    def get_context() -> dict[str, Any]:
        """Get the compact context pack — a whole repo's understanding in one
        call (identity, counts, key files, layers, conventions, dependencies,
        decisions, history). The most token-efficient starting point."""
        return tools.get_context(root)

    @server.tool()
    def get_project_summary() -> dict[str, Any]:
        """Get the project's identity: language, framework, package manager,
        file/module/dependency counts, entry points, and conventions."""
        return tools.get_project_summary(root)

    @server.tool()
    def get_architecture() -> dict[str, Any]:
        """Get the architecture overview: style, layers, languages, frameworks,
        databases, and the key (most-imported) files."""
        return tools.get_architecture(root)

    @server.tool()
    def get_knowledge() -> dict[str, Any]:
        """Get the knowledge layer: recorded/discovered architecture decisions,
        the patterns the codebase follows, and its git history. Use this to
        understand the *why* and the project's evolution, not just its structure."""
        return tools.get_knowledge(root)

    @server.tool()
    def get_conventions() -> dict[str, Any]:
        """Get the repository's coding conventions: file/class/function naming
        styles, source layout, dependency-injection framework, architectural
        layering, structural patterns, and the testing setup. Use this to write
        new code that matches how the team already writes it."""
        return tools.get_conventions(root)

    @server.tool()
    def get_module_info(module: str | None = None) -> dict[str, Any]:
        """Get details for a module (files, LOC, classes, functions, imports).
        Pass a module path/name, or omit it to list all modules."""
        return tools.get_module_info(root, module)

    @server.tool()
    def get_feature(name: str) -> dict[str, Any]:
        """Describe a whole feature (e.g. "auth", "calendars") that spans several
        directories: combined size, its sub-modules, what it depends on outside
        itself, and who depends on it. Use this instead of get_module_info when a
        feature is split across bloc/data/presentation folders."""
        return tools.get_feature(root, name)

    @server.tool()
    def get_dependencies() -> dict[str, Any]:
        """List declared third-party dependencies with versions and dev flags."""
        return tools.get_dependencies(root)

    @server.tool()
    def get_health() -> dict[str, Any]:
        """Report how much of the repo the graph actually resolved: overall
        confidence, connected vs. isolated files, per-language coverage
        (graphed vs. inventory-only), and warnings. Check this before trusting a
        "safe to change" / "no consumers" verdict — low confidence means imports
        may be unresolved and impact results under-report."""
        return tools.get_health(root)

    @server.tool()
    def get_critical_files(limit: int = 10) -> dict[str, Any]:
        """List the most-depended-on files (highest import in-degree) — the
        files most risky to change."""
        return tools.get_critical_files(root, limit)

    @server.tool()
    def get_hotspots(limit: int = 10) -> dict[str, Any]:
        """List risk hotspots: files ranked by git churn × import in-degree — the
        ones that both change often and are widely depended on. A sharper "what's
        risky here" signal than in-degree alone. Requires git history; test/spec
        files are excluded."""
        return tools.get_hotspots(root, limit)

    @server.tool()
    def explain_module(target: str) -> dict[str, Any]:
        """Explain a module by path or name (e.g. "auth"): its purpose,
        dependencies, consumers, critical files, blast radius, and a risk
        assessment for changing it. Generated from memory, no LLM."""
        return tools.explain_module(root, target)

    @server.tool()
    def find_symbol(name: str) -> dict[str, Any]:
        """Locate a class, function, or method by name: the file and line it's
        defined at, and who references it. Use this instead of grepping +
        reading files to answer "where is X defined / who calls it?"."""
        return tools.find_symbol(root, name)

    @server.tool()
    def what_tests(target: str) -> dict[str, Any]:
        """List the test files that cover a source file (by path or name): the
        tests to run before/after editing it. Found via tests that import the
        file and by test-name convention."""
        return tools.what_tests(root, target)

    @server.tool()
    def analyze_impact(target: str) -> dict[str, Any]:
        """Predict the impact of changing a file by path or name (e.g.
        "auth_service.py"): the files that transitively import it, the modules
        they span, and a risk level. Call this before editing a file."""
        return tools.analyze_impact(root, target)

    return server


def run(root: Path, transport: str = "stdio") -> None:
    """Build and run the server (blocking)."""
    build_server(root).run(transport=transport)


__all__ = ["build_server", "run"]
