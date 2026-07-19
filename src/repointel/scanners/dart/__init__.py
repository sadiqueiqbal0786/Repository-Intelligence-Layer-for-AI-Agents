"""Dart / Flutter ecosystem scanner.

pubspec.yaml is parsed with a lightweight text scan rather than a YAML library
so RepoIntel stays dependency-light for Phase 1. The fields we need
(dependency names, the flutter SDK marker) are unambiguous at the text level.
"""

from __future__ import annotations

from repointel.models import Dependency, Fingerprint
from repointel.scanners.base import RepoContext

_STATE_MANAGEMENT: list[tuple[str, str]] = [
    ("flutter_riverpod", "Riverpod"),
    ("riverpod", "Riverpod"),
    ("flutter_bloc", "BLoC"),
    ("bloc", "BLoC"),
    ("provider", "Provider"),
    ("get:", "GetX"),
    ("get_it", "GetIt"),
    ("mobx", "MobX"),
    ("redux", "Redux"),
]

_NAVIGATION: list[tuple[str, str]] = [
    ("go_router", "GoRouter"),
    ("auto_route", "AutoRoute"),
    ("beamer", "Beamer"),
    ("fluro", "Fluro"),
]

_DATABASES: list[tuple[str, str]] = [
    ("cloud_firestore", "Cloud Firestore"),
    ("firebase_database", "Firebase Realtime DB"),
    ("sqflite", "SQLite"),
    ("drift", "Drift (SQLite)"),
    ("isar", "Isar"),
    ("hive", "Hive"),
    ("objectbox", "ObjectBox"),
    ("realm", "Realm"),
]


def _primary_pubspec(ctx: RepoContext) -> str | None:
    """Locate the repo's main ``pubspec.yaml``, at the root OR in a subfolder.

    A Flutter project often lives under ``app/`` (or similar), so assuming the
    manifest is at the root left the whole ecosystem undetected (framework,
    package manager, dependencies, databases). Prefer a root manifest; otherwise
    pick the shallowest one, ignoring vendored/generated trees.
    """
    if ctx.exists("pubspec.yaml"):
        return "pubspec.yaml"
    candidates = [
        rel for rel, _ in ctx.files()
        if rel == "pubspec.yaml" or rel.endswith("/pubspec.yaml")
    ]
    if not candidates:
        return None
    # Shallowest, then lexical — deterministic across runs.
    return min(candidates, key=lambda p: (p.count("/"), p))


class DartScanner:
    name = "dart"

    def matches(self, ctx: RepoContext) -> bool:
        return _primary_pubspec(ctx) is not None

    def fingerprint(self, ctx: RepoContext, fp: Fingerprint) -> None:
        pubspec_path = _primary_pubspec(ctx)
        pubspec = (ctx.read_text(pubspec_path) or "").lower() if pubspec_path else ""
        src = pubspec_path or "pubspec.yaml"

        is_flutter = "sdk: flutter" in pubspec or "flutter:" in pubspec
        fp.set("language", "Dart", src)
        fp.set(
            "framework",
            "Flutter" if is_flutter else "Dart",
            f"flutter SDK in {src}" if is_flutter else "pure Dart package",
        )
        fp.set("package_manager", "pub", src)
        fp.set("build_system", "Flutter SDK" if is_flutter else "Dart SDK", src)

        for needle, label in _STATE_MANAGEMENT:
            if needle in pubspec:
                fp.set("state_management", label, f"dependency '{needle.rstrip(':')}'")
                break

        for needle, label in _NAVIGATION:
            if needle in pubspec:
                fp.set("navigation", label, f"dependency '{needle}'")
                break

        seen: set[str] = set()
        for needle, label in _DATABASES:
            if needle in pubspec and label not in seen:
                seen.add(label)
                fp.databases.append(label)
        if fp.databases:
            fp.evidence["databases"] = f"{src} dependencies"

    # ---- Phase 2: inventory --------------------------------------------------

    def dependencies(self, ctx: RepoContext) -> list[Dependency]:
        pubspec_path = _primary_pubspec(ctx)
        raw = ctx.read_text(pubspec_path) if pubspec_path else None
        if not raw:
            return []
        src = f"{pubspec_path} " if pubspec_path != "pubspec.yaml" else ""
        deps: list[Dependency] = []
        deps.extend(self._parse_section(raw, "dependencies", dev=False, src_prefix=src))
        deps.extend(self._parse_section(raw, "dev_dependencies", dev=True, src_prefix=src))
        return deps

    def entry_points(self, ctx: RepoContext) -> list[str]:
        # The package's lib/ (and bin/) live alongside its pubspec — which may be
        # in a subfolder, so resolve relative to that, not the repo root.
        pubspec_path = _primary_pubspec(ctx)
        base = pubspec_path[: -len("pubspec.yaml")] if pubspec_path else ""
        candidates = [f"{base}lib/main.dart", f"{base}bin/main.dart"]
        found = [rel for rel in candidates if ctx.exists(rel)]
        found.extend(
            rel for rel, _ in ctx.files()
            if rel.startswith(f"{base}bin/") and rel.endswith(".dart")
        )
        return sorted(set(found))

    def _parse_section(
        self, raw: str, section: str, *, dev: bool, src_prefix: str = ""
    ) -> list[Dependency]:
        """Extract top-level keys under a pubspec ``dependencies:`` block.

        Handles both ``pkg: ^1.2.3`` and the nested SDK form (``flutter:\\n  sdk:
        flutter``), where the version is absent.
        """
        deps: list[Dependency] = []
        in_section = False
        for line in raw.splitlines():
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                in_section = stripped.rstrip(":").strip() == section
                continue
            if not in_section:
                continue
            # Top-level dependency entries sit one level in (2 spaces by convention).
            if indent <= 2:
                key, _, value = stripped.strip().partition(":")
                key = key.strip()
                if not key:
                    continue
                version = value.strip() or None
                source = f"{src_prefix}pubspec.yaml [{section}]"
                deps.append(Dependency(name=key, version=version, source=source, dev=dev))
        return deps
