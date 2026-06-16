"""Token-savings benchmark (Phase 12).

Quantifies the platform's core promise: an agent that loads the context pack
understands a repository for a fraction of the tokens it would spend reading the
source. For a repo we measure the raw source size, the pack size, and the
resulting compression ratio — the headline number for adopters and contributors.

Token counts are estimates (~4 chars/token); they are for *comparison*, not
billing, and the ratio is stable regardless of the exact tokenizer.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from repointel.context.compression import (
    build_context_pack,
    estimate_tokens,
    estimate_tokens_for_chars,
)
from repointel.context.memory import build_memory
from repointel.models import BenchmarkResult


def benchmark_repo(root: Path) -> BenchmarkResult:
    """Build memory for ``root`` and measure raw-vs-pack token savings."""
    root = Path(root)

    start = perf_counter()
    bundle = build_memory(root)
    analyze_seconds = perf_counter() - start

    source = [f for f in bundle.inventory.files if f.language]
    source_bytes = sum(f.size for f in source)
    source_loc = sum(f.loc for f in source)

    pack = build_context_pack(
        bundle.repo,
        bundle.architecture,
        bundle.modules,
        bundle.conventions,
        bundle.knowledge,
        bundle.inventory,
    )
    raw_tokens = estimate_tokens_for_chars(source_bytes)
    pack_tokens = estimate_tokens(pack.model_dump_json())
    ratio = (raw_tokens / pack_tokens) if pack_tokens else 0.0

    return BenchmarkResult(
        repo=bundle.repo.name,
        source_files=len(source),
        source_loc=source_loc,
        source_bytes=source_bytes,
        raw_tokens_est=raw_tokens,
        pack_tokens_est=pack_tokens,
        compression_ratio=round(ratio, 1),
        tokens_saved_est=max(0, raw_tokens - pack_tokens),
        analyze_seconds=round(analyze_seconds, 3),
    )


def benchmark_repos(roots: list[Path]) -> list[BenchmarkResult]:
    return [benchmark_repo(root) for root in roots]


__all__ = ["benchmark_repo", "benchmark_repos"]
