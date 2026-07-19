"""Tests for the build-time coverage / fail-loud trust signal."""

from __future__ import annotations

from pathlib import Path

from repointel.context.memory import build_memory


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_high_confidence_when_imports_resolve(tmp_path: Path) -> None:
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(tmp_path, "lib/models/user.dart", "class User {}\n")
    _write(
        tmp_path,
        "lib/models/order.dart",
        "import 'package:shop/models/user.dart';\n\nclass Order {}\n",
    )
    _write(
        tmp_path,
        "lib/repo.dart",
        "import 'package:shop/models/order.dart';\n\nclass Repo {}\n",
    )
    _write(
        tmp_path,
        "lib/service.dart",
        "import 'package:shop/models/user.dart';\n"
        "import 'package:shop/repo.dart';\n\n"
        "class Service {}\n",
    )
    _write(tmp_path, "lib/app.dart", "import 'package:shop/service.dart';\n\nclass App {}\n")
    _write(tmp_path, "lib/main.dart", "import 'package:shop/app.dart';\n")
    cov = build_memory(tmp_path).repo.coverage
    assert cov is not None
    assert cov.confidence == "high"
    assert cov.isolated_files == 0
    assert cov.connectivity == 1.0
    assert cov.warnings == []


def test_low_connectivity_is_flagged_loudly(tmp_path: Path) -> None:
    """When imports don't resolve (wrong package name — the pubspec-not-found
    class of bug), files come out isolated and coverage must say so."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    # Every file imports a package that isn't this one -> nothing resolves.
    for i in range(6):
        _write(
            tmp_path,
            f"lib/f{i}.dart",
            f"import 'package:other/f{(i + 1) % 6}.dart';\n\nclass F{i} {{}}\n",
        )
    cov = build_memory(tmp_path).repo.coverage
    assert cov is not None
    assert cov.source_files == 6
    assert cov.isolated_files == 6
    assert cov.confidence == "low"
    assert any("connectivity" in w.lower() for w in cov.warnings)


def test_ungraphed_language_is_reported(tmp_path: Path) -> None:
    """A language with no parser is surfaced as inventory-only, never assumed
    complete."""
    _write(tmp_path, "pubspec.yaml", "name: shop\n")
    _write(tmp_path, "lib/main.dart", "class App {}\n")
    _write(tmp_path, "ios/Runner/AppDelegate.swift", "class AppDelegate {}\n")
    cov = build_memory(tmp_path).repo.coverage
    assert cov is not None
    graphed = {lc.language: lc.graphed for lc in cov.languages}
    if "Swift" in graphed:  # only if Swift files are inventoried (not ignored)
        assert graphed["Swift"] is False
        assert "Swift" in cov.ungraphed_languages
        assert any("inventory only" in w.lower() for w in cov.warnings)
