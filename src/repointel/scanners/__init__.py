"""Scanner layer — per-language analysis of a repository.

Public surface:
- :data:`SCANNERS` — the registry of implemented scanners.
- :func:`fingerprint_repo` — Phase 1 fingerprint.
- :func:`scan_repo` — Phase 2 full inventory.
- :class:`RepoContext`, :class:`Scanner` — the extension seam for new languages.
"""

from __future__ import annotations

from repointel.scanners.base import RepoContext, Scanner
from repointel.scanners.orchestrator import fingerprint_repo, resolve_project_root, scan_repo
from repointel.scanners.registry import SCANNERS

__all__ = [
    "SCANNERS",
    "RepoContext",
    "Scanner",
    "fingerprint_repo",
    "resolve_project_root",
    "scan_repo",
]
