"""Built-in language plugins shipped with RepoIntel (Phase 10)."""

from __future__ import annotations

from repointel.plugins.base import LanguagePlugin
from repointel.plugins.builtin.dart import dart_plugin
from repointel.plugins.builtin.python import python_plugin


def builtin_plugins() -> list[LanguagePlugin]:
    """The plugins always available, in priority order."""
    return [python_plugin, dart_plugin]


__all__ = ["builtin_plugins", "dart_plugin", "python_plugin"]
