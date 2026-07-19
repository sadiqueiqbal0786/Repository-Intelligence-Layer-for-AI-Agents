"""Tests for the Phase 12 platform layer (compression + benchmark)."""

from __future__ import annotations

from pathlib import Path

from repointel.context.benchmark import benchmark_repo
from repointel.context.compression import (
    build_context_pack,
    context_pack,
    estimate_tokens,
    render_context_markdown,
)
from repointel.context.memory import build_memory


def _write(root: Path, rel: str, content: str = "") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _project(root: Path) -> None:
    _write(root, "pyproject.toml", '[project]\nname = "demo"\ndependencies = ["fastapi>=0.110"]\n')
    _write(root, "src/demo/__init__.py", "")
    _write(root, "src/demo/models.py", "class User:\n    pass\n")
    _write(
        root,
        "src/demo/repository.py",
        "from demo.models import User\n\n\nclass UserRepository:\n    pass\n",
    )


def _large_project(root: Path) -> None:
    """A project whose source dwarfs its summary, so compression is real."""
    _write(root, "pyproject.toml", '[project]\nname = "big"\ndependencies = ["fastapi"]\n')
    body = "\n".join(f"    def method_{i}(self):\n        return {i}" for i in range(20))
    for n in range(8):
        _write(root, f"src/big/mod_{n}.py", f"class Service{n}:\n{body}\n")


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1  # 4 chars ~ 1 token
    assert estimate_tokens("a" * 10) == 3  # ceil(10/4)


def test_build_context_pack_fields(tmp_path: Path) -> None:
    _project(tmp_path)
    bundle = build_memory(tmp_path)
    pack = build_context_pack(
        bundle.repo,
        bundle.architecture,
        bundle.modules,
        bundle.conventions,
        bundle.knowledge,
        bundle.inventory,
    )
    assert pack.name == tmp_path.name
    assert pack.framework == "FastAPI"
    assert pack.class_naming == "PascalCase"
    assert "fastapi" in pack.top_dependencies
    assert pack.patterns  # inferred patterns carried through
    # Provenance: identity facts cite where they came from.
    assert pack.provenance.get("framework")  # e.g. the fastapi dependency
    assert pack.confidence in {"high", "medium", "low", "unknown"}


def test_render_markdown_has_sections(tmp_path: Path) -> None:
    _project(tmp_path)
    pack = context_pack(tmp_path)
    assert pack is not None
    md = render_context_markdown(pack)
    assert md.startswith(f"# {tmp_path.name}")
    assert "## Conventions" in md
    assert "## Top dependencies" in md


def test_context_pack_builds_memory_on_first_call(tmp_path: Path) -> None:
    _project(tmp_path)
    pack = context_pack(tmp_path)  # no prior build
    assert pack is not None
    assert pack.file_count >= 3


def test_benchmark_reports_compression(tmp_path: Path) -> None:
    _large_project(tmp_path)
    result = benchmark_repo(tmp_path)
    assert result.source_files == 8
    assert result.raw_tokens_est > 0
    assert result.pack_tokens_est > 0
    # The pack is smaller than the raw source -> real savings.
    assert result.pack_tokens_est < result.raw_tokens_est
    assert result.compression_ratio > 1
    assert result.tokens_saved_est == result.raw_tokens_est - result.pack_tokens_est


def test_benchmark_does_not_persist(tmp_path: Path) -> None:
    _project(tmp_path)
    benchmark_repo(tmp_path)
    # Benchmarking builds memory in-process only; it must not write artifacts.
    assert not (tmp_path / ".repointel").exists()
