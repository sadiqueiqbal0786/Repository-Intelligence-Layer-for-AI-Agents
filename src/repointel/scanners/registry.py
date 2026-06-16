"""The scanner registry.

For Phase 1/2 this is a static list of implemented scanners. Phase 10 will load
third-party scanners here (e.g. via entry points) without touching the
orchestrator. TypeScript/Java exist as stubs and join the list once their
detection logic lands.
"""

from __future__ import annotations

from repointel.scanners.base import Scanner
from repointel.scanners.dart import DartScanner
from repointel.scanners.python import PythonScanner

SCANNERS: list[Scanner] = [
    PythonScanner(),
    DartScanner(),
]
