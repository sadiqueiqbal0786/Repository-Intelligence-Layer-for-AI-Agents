"""The built-in scanner list.

The orchestrator now sources scanners from the Phase 10 plugin registry
(:func:`repointel.plugins.default_registry`), which also discovers third-party
scanners via entry points. This list remains the canonical set of built-in
scanners and a stable import for callers that want them directly.
TypeScript/Java exist as stubs and join once their detection logic lands.
"""

from __future__ import annotations

from repointel.scanners.base import Scanner
from repointel.scanners.dart import DartScanner
from repointel.scanners.python import PythonScanner

SCANNERS: list[Scanner] = [
    PythonScanner(),
    DartScanner(),
]
