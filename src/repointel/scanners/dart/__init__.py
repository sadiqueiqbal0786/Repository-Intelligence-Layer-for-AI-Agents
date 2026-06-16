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


class DartScanner:
    name = "dart"

    def matches(self, ctx: RepoContext) -> bool:
        return ctx.exists("pubspec.yaml")

    def fingerprint(self, ctx: RepoContext, fp: Fingerprint) -> None:
        pubspec = (ctx.read_text("pubspec.yaml") or "").lower()

        is_flutter = "sdk: flutter" in pubspec or "flutter:" in pubspec
        fp.set("language", "Dart", "pubspec.yaml")
        fp.set(
            "framework",
            "Flutter" if is_flutter else "Dart",
            "flutter SDK in pubspec.yaml" if is_flutter else "pure Dart package",
        )
        fp.set("package_manager", "pub", "pubspec.yaml")
        fp.set("build_system", "Flutter SDK" if is_flutter else "Dart SDK", "pubspec.yaml")

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
            fp.evidence["databases"] = "pubspec.yaml dependencies"

    # ---- Phase 2: inventory --------------------------------------------------

    def dependencies(self, ctx: RepoContext) -> list[Dependency]:
        raw = ctx.read_text("pubspec.yaml")
        if not raw:
            return []
        deps: list[Dependency] = []
        deps.extend(self._parse_section(raw, "dependencies", dev=False))
        deps.extend(self._parse_section(raw, "dev_dependencies", dev=True))
        return deps

    def entry_points(self, ctx: RepoContext) -> list[str]:
        candidates = ["lib/main.dart", "bin/main.dart"]
        found = [rel for rel in candidates if ctx.exists(rel)]
        found.extend(
            rel for rel, _ in ctx.files() if rel.startswith("bin/") and rel.endswith(".dart")
        )
        return sorted(set(found))

    def _parse_section(self, raw: str, section: str, *, dev: bool) -> list[Dependency]:
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
                source = f"pubspec.yaml [{section}]"
                deps.append(Dependency(name=key, version=version, source=source, dev=dev))
        return deps
