"""Convention discovery (Phase 6).

Teaches agents *how the team writes code*. Beyond the Phase 4 baseline (source
layout, file naming, testing) this infers identifier-casing conventions for
classes and functions from the graph, the dependency-injection / wiring
framework in use, the recurring layer directories that reveal the
decomposition, and the structural patterns those layers imply.

Every signal is derived — never guessed — so a value is only emitted when the
evidence clears a majority threshold (casing) or an explicit marker is present
(DI, layering, patterns).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from repointel.models import (
    ArchitectureGraph,
    Conventions,
    NamingConventions,
    RepositoryInventory,
    TestingConvention,
)

_TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.(py|dart|go|js|ts)$")
_SNAKE_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_CAMEL_RE = re.compile(r"^[a-z]+([A-Z][a-z0-9]*)+$")
_PASCAL_RE = re.compile(r"^[A-Z][a-z0-9]+([A-Z][a-z0-9]*)*$")
_SCREAMING_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")

# Fraction of samples that must share a style before we name it (else "mixed").
_MAJORITY = 0.6

# Dependency-name needle (lowercased substring) -> DI / wiring framework label.
# Order matters: the first match wins, so list the more specific needles first.
_DI_FRAMEWORKS: list[tuple[str, str]] = [
    # Python
    ("dependency-injector", "dependency-injector"),
    ("dependency_injector", "dependency-injector"),
    ("fastapi", "FastAPI"),
    ("flask-injector", "Flask-Injector"),
    # Dart / Flutter
    ("flutter_riverpod", "Riverpod"),
    ("riverpod", "Riverpod"),
    ("injectable", "injectable"),
    ("get_it", "get_it"),
    ("provider", "Provider"),
    # TypeScript / JavaScript
    ("@nestjs/core", "NestJS"),
    ("inversify", "InversifyJS"),
    ("tsyringe", "tsyringe"),
    ("typedi", "TypeDI"),
    # Java / Kotlin
    ("spring-boot", "Spring"),
    ("spring-context", "Spring"),
    ("dagger", "Dagger"),
    ("guice", "Guice"),
]

# Directory-segment names that mark an architectural layer. Matched as exact
# normalized segments; ``patterns`` derives higher-level meaning from these.
_LAYER_NAMES = frozenset(
    {
        "domain",
        "data",
        "presentation",
        "application",
        "infrastructure",
        "controllers",
        "controller",
        "services",
        "service",
        "repositories",
        "repository",
        "repositorys",
        "models",
        "model",
        "views",
        "view",
        "entities",
        "entity",
        "usecases",
        "use_cases",
        "handlers",
        "handler",
        "routes",
        "router",
        "schemas",
        "schema",
        "dto",
        "dtos",
        "adapters",
        "adapter",
    }
)


def detect_conventions(
    inventory: RepositoryInventory, graph: ArchitectureGraph | None = None
) -> Conventions:
    fp = inventory.fingerprint
    file_naming = _file_naming(inventory)
    naming = NamingConventions(
        files=file_naming,
        classes=_symbol_naming(graph, "class"),
        functions=_symbol_naming(graph, "function"),
    )
    segments = _path_segments(inventory)
    return Conventions(
        architecture=fp.architecture,
        source_layout=_source_layout(inventory),
        package_manager=fp.package_manager,
        build_system=fp.build_system,
        file_naming=file_naming,
        naming=naming,
        dependency_injection=_dependency_injection(inventory),
        layering=_layering(segments),
        patterns=_patterns(inventory, segments | _file_tokens(inventory)),
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
    return _dominant(counts)


def _symbol_naming(graph: ArchitectureGraph | None, kind: str) -> str | None:
    """Dominant casing style across graph nodes of ``kind`` (class/function)."""
    if graph is None:
        return None
    counts = {"snake_case": 0, "camelCase": 0, "PascalCase": 0, "SCREAMING_SNAKE": 0, "other": 0}
    measured = 0
    for node in graph.nodes:
        if node.kind != kind:
            continue
        # Methods are stored as "Class.method"; classify the member identifier.
        ident = node.name.rsplit(".", 1)[-1]
        style = _identifier_style(ident)
        if style is None:
            continue  # dunders / language-mandated names carry no team signal
        counts[style] += 1
        measured += 1
    return _dominant(counts) if measured else None


def _identifier_style(name: str) -> str | None:
    """Classify an identifier's casing, or ``None`` to skip it."""
    core = name.strip("_")
    if not core:
        return None  # all underscores
    # Dunder / language-mandated names (``__init__``, ``__str__``) aren't a choice.
    if name.startswith("__") and name.endswith("__"):
        return None
    if "_" in core and _SCREAMING_RE.match(core):
        return "SCREAMING_SNAKE"
    if _PASCAL_RE.match(core):
        return "PascalCase"
    if _CAMEL_RE.match(core):
        return "camelCase"
    if _SNAKE_RE.match(core):
        return "snake_case"
    return "other"


def _dependency_injection(inventory: RepositoryInventory) -> str | None:
    names = " ".join(d.name.lower() for d in inventory.dependencies)
    for needle, label in _DI_FRAMEWORKS:
        if needle in names:
            return label
    # Flutter state managers double as wiring; the fingerprint records them.
    sm = inventory.fingerprint.state_management
    if sm and sm.lower() in {"riverpod", "provider", "getx", "bloc"}:
        return sm
    return None


def _path_segments(inventory: RepositoryInventory) -> set[str]:
    """Lowercased directory segments, with the source root stripped."""
    segments: set[str] = set()
    for directory in inventory.directories:
        parts = [p for p in directory.split("/") if p]
        if parts and parts[0] in {"src", "lib", "app"}:
            parts = parts[1:]
        segments.update(p.lower() for p in parts)
    return segments


def _file_tokens(inventory: RepositoryInventory) -> set[str]:
    """Lowercased tokens from source-file stems (e.g. ``order_repository`` ->
    ``order``, ``repository``). Catches suffix conventions like ``*_service``."""
    tokens: set[str] = set()
    for entry in inventory.files:
        if not entry.language:
            continue
        stem = PurePosixPath(entry.path).stem.lower()
        tokens.add(stem)
        tokens.update(re.split(r"[_-]", stem))
    return {t for t in tokens if t}


def _layering(segments: set[str]) -> list[str]:
    return sorted(segments & _LAYER_NAMES)


def _patterns(inventory: RepositoryInventory, segments: set[str]) -> list[str]:
    found: list[str] = []
    if any(s.startswith("repositor") for s in segments):
        found.append("repository_pattern")
    if any(s.startswith("service") for s in segments):
        found.append("service_layer")
    if any(s.startswith("controller") for s in segments):
        found.append("controller_layer")
    if "usecases" in segments or "use_cases" in segments:
        found.append("use_case_pattern")
    if {"features", "modules"} & segments:
        found.append("feature_modules")
    if _dependency_injection(inventory) is not None:
        found.append("dependency_injection")
    return found


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


def _dominant(counts: dict[str, int]) -> str | None:
    """The majority style in ``counts``, ``"mixed"`` if none dominates, else ``None``."""
    total = sum(counts.values())
    if total == 0:
        return None
    label, top = max(counts.items(), key=lambda kv: kv[1])
    if label == "other":
        return "mixed"
    return label if top / total >= _MAJORITY else "mixed"


__all__ = ["detect_conventions"]
