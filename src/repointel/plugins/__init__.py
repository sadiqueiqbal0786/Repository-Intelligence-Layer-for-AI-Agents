"""Plugin layer — the multi-language extension ecosystem (Phase 10).

Public surface:
- :class:`LanguagePlugin` / :class:`Plugin` / :class:`Parser` — the contract a
  language plugin implements.
- :class:`PluginRegistry`, :func:`default_registry` — the runtime registry the
  scanners and graph builder consult.
- :func:`register_plugin` — drop a plugin in at runtime; package authors instead
  advertise the ``repointel.plugins`` entry-point group for auto-discovery.
"""

from __future__ import annotations

from repointel.plugins.base import LanguagePlugin, Parser, Plugin
from repointel.plugins.registry import (
    ENTRY_POINT_GROUP,
    PluginRegistry,
    default_registry,
    discover_plugins,
    register_plugin,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "LanguagePlugin",
    "Parser",
    "Plugin",
    "PluginRegistry",
    "default_registry",
    "discover_plugins",
    "register_plugin",
]
