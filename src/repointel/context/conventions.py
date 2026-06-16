"""Lightweight convention detection (Phase 4 baseline; deepened in Phase 6).

Infers source layout, file-naming style, and the testing setup from the
inventory. Phase 6 will extend this with dependency-injection patterns,
architectural rules, and naming conventions for classes/functions.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from repointel.models import Conventions, RepositoryInventory, TestingConvention

_TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.(py|dart|go|js|ts)$")
_SNAKE_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_CAMEL_RE = re.compile(r"^[a-z]+([A-Z][a-z0-9]*)+$")


def detect_conventions(inventory: RepositoryInventory) -> Conventions:
    fp = inventory.fingerprint
    return Conventions(
        architecture=fp.architecture,
        source_layout=_source_layout(inventory),
        package_manager=fp.package_manager,
        build_system=fp.build_system,
        file_naming=_file_naming(inventory),
        testing=_testing(inventory),
    )


def _source_layout(inventory: RepositoryInventory) -> str:
    paths = [m.path for m in inventory.modules]
    if any(p == "src" or p.startswith("src/") for p in paths):
        return "src"
    if any(p == "lib" or p.startswith("lib/") for p in paths):
        return "lib"
    return "flat"


def _file_naming(inventory: RepositoryInventory) -> str | None:
    counts = {"snake_case": 0, "kebab-case": 0, "camelCase": 0, "other": 0}
    for entry in inventory.files:
        if not entry.language:
            continue
        stem = PurePosixPath(entry.path).stem
        if _SNAKE_RE.match(stem) and "_" in stem:
            counts["snake_case"] += 1
        elif _KEBAB_RE.match(stem) and "-" in stem:
            counts["kebab-case"] += 1
        elif _CAMEL_RE.match(stem):
            counts["camelCase"] += 1
        elif _SNAKE_RE.match(stem):
            counts["snake_case"] += 1  # single lowercase word
        else:
            counts["other"] += 1
    total = sum(counts.values())
    if total == 0:
        return None
    dominant, top = max(counts.items(), key=lambda kv: kv[1])
    # Require a clear majority, else call it mixed.
    return dominant if top / total >= 0.6 else "mixed"


def _testing(inventory: RepositoryInventory) -> TestingConvention:
    dep_names = {d.name.lower() for d in inventory.dependencies}
    framework: str | None = None
    if "pytest" in dep_names:
        framework = "pytest"
    elif "flutter_test" in dep_names:
        framework = "flutter_test"

    test_files = [f.path for f in inventory.files if _TEST_FILE_RE.search(f.path)]
    if framework is None and test_files:
        framework = "unittest" if any(f.endswith(".py") for f in test_files) else None

    test_dir = None
    for directory in sorted(inventory.directories):
        name = PurePosixPath(directory).name
        if name in {"test", "tests"}:
            test_dir = directory
            break

    return TestingConvention(framework=framework, test_dir=test_dir, test_count=len(test_files))


__all__ = ["detect_conventions"]
