"""Smoke tests for the RepoIntel CLI (Phase 0)."""

from __future__ import annotations

from typer.testing import CliRunner

from repointel import __version__
from repointel.cli import app

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Repository Intelligence Engine" in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # no_args_is_help shows usage and exits with code 2 (Typer treats a bare
    # invocation as a usage error).
    assert result.exit_code == 2
    assert "Usage" in result.output


def test_analyze_empty_dir(tmp_path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "No recognizable ecosystem detected" in result.output


def test_analyze_json_output(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    result = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"language": "Python"' in result.output
