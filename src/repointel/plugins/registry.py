"""Plugin registry + discovery (Phase 10).

The registry aggregates built-in plugins with any third-party plugins advertised
under the ``repointel.plugins`` entry-point group, so installing a package is
enough to teach RepoIntel a new language — no core file changes. A malformed or
crashing third-party plugin is skipped, never fatal.

``default_registry()`` is the process-wide instance the scanners and graph
builder consult; it is cached after first use.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points

from repointel.plugins.base import LanguagePlugin, Parser
from repointel.scanners.base import Scanner

ENTRY_POINT_GROUP = "repointel.plugins"


class PluginRegistry:
    """Holds the active plugins and answers per-language lookups."""

    def __init__(self, plugins: list[LanguagePlugin] | None = None) -> None:
        self._plugins: list[LanguagePlugin] = list(plugins or [])

    def register(self, plugin: LanguagePlugin) -> None:
        """Add a plugin at runtime (front of the list — wins ties)."""
        self._plugins.insert(0, plugin)

    def plugins(self) -> list[LanguagePlugin]:
        return list(self._plugins)

    def scanners(self) -> list[Scanner]:
        return [p.scanner for p in self._plugins if p.scanner is not None]

    def parsers(self) -> list[Parser]:
        return [p.parser for p in self._plugins if p.parser is not None]

    def parser_for(self, language: str | None) -> Parser | None:
        """The first parser that handles ``language`` (built-ins win)."""
        if not language:
            return None
        for plugin in self._plugins:
            if plugin.parser is not None and plugin.parser.language == language:
                return plugin.parser
        return None

    def parseable_languages(self) -> set[str]:
        return {p.parser.language for p in self._plugins if p.parser is not None}


def discover_plugins() -> list[LanguagePlugin]:
    """Load plugins from the ``repointel.plugins`` entry-point group.

    Each entry point resolves to a :class:`LanguagePlugin`, or to a zero-arg
    callable (class or factory) that returns one.
    """
    found: list[LanguagePlugin] = []
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception:
        return found
    for ep in eps:
        try:
            obj = ep.load()
            found.append(obj() if callable(obj) else obj)
        except Exception:
            continue  # a broken third-party plugin must not break the core
    return found


@lru_cache(maxsize=1)
def default_registry() -> PluginRegistry:
    """The shared registry: built-in plugins first, then discovered ones."""
    from repointel.plugins.builtin import builtin_plugins

    return PluginRegistry([*builtin_plugins(), *discover_plugins()])


def register_plugin(plugin: LanguagePlugin) -> None:
    """Register a plugin onto the default registry (the in-process drop-in path)."""
    default_registry().register(plugin)


__all__ = [
    "ENTRY_POINT_GROUP",
    "PluginRegistry",
    "default_registry",
    "discover_plugins",
    "register_plugin",
]
