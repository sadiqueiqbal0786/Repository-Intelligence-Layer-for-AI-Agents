"""Tests for the accuracy eval harness."""

from __future__ import annotations

from pathlib import Path

from repointel.context.eval import build_reference_repo, default_cases, run_eval


def test_reference_repo_scores_full_accuracy(tmp_path: Path) -> None:
    """The known-answer fixture must pass every check — this is the regression
    guard: if a change breaks a tool's accuracy, this drops below 100%."""
    root = build_reference_repo(tmp_path)
    report = run_eval(root)
    failures = [r.name for r in report.results if not r.passed]
    assert report.accuracy == 1.0, f"failed checks: {failures} ({report.results})"
    assert report.total == len(default_cases())


def test_eval_reports_tokens(tmp_path: Path) -> None:
    root = build_reference_repo(tmp_path)
    report = run_eval(root)
    # Both are measured (reduction only exceeds 1x at real scale; the fixture is
    # deliberately tiny, so we assert the accounting exists, not its ratio).
    assert report.context_tokens > 0
    assert report.raw_tokens > 0
    assert report.token_reduction > 0


def test_failing_case_lowers_accuracy(tmp_path: Path) -> None:
    from repointel.context.eval import EvalCase

    root = build_reference_repo(tmp_path)
    always_fail = EvalCase("bogus", "impossible?", lambda _root: (False, "nope"))
    report = run_eval(root, cases=[*default_cases(), always_fail])
    assert report.passed == report.total - 1
    assert report.accuracy < 1.0
