"""Accuracy eval harness — the one benchmark that actually proves the product.

Token-reduction alone flatters a tool that is cheap but wrong: if the answers
are inaccurate a cold agent re-verifies with grep and the "reduction" goes
negative. So this measures **accuracy** (did RepoIntel answer correctly?)
*alongside* tokens, against a fixture whose ground truth is known independently
of the memory being tested.

It doubles as a regression guard (accuracy must not drop) and a roadmap compass
(the questions it fails are the backlog). ``default_cases`` is meant to grow —
add a case for every real task you want an agent to be able to do from memory.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from repointel.context.compression import estimate_tokens, render_context_markdown
from repointel.mcp import tools


@dataclass
class EvalCase:
    """One question with a checker that queries RepoIntel and grades the answer."""

    name: str
    question: str
    check: Callable[[Path], tuple[bool, str]]


@dataclass
class EvalResult:
    name: str
    question: str
    passed: bool
    detail: str


@dataclass
class EvalReport:
    total: int
    passed: int
    results: list[EvalResult] = field(default_factory=list)
    context_tokens: int = 0
    raw_tokens: int = 0

    @property
    def accuracy(self) -> float:
        return round(self.passed / self.total, 3) if self.total else 0.0

    @property
    def token_reduction(self) -> float:
        return round(self.raw_tokens / self.context_tokens, 1) if self.context_tokens else 0.0


def _w(root: Path, rel: str, content: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_reference_repo(root: Path) -> Path:
    """A small project whose answers are known by construction (the ground truth)."""
    _w(root, "pyproject.toml", '[project]\nname = "shop"\ndependencies = ["fastapi>=0.110"]\n')
    _w(root, "src/shop/__init__.py", "")
    _w(root, "src/shop/models.py", "class User:\n    pass\n")
    _w(
        root,
        "src/shop/repository.py",
        "from shop.models import User\n\n\nclass UserRepository:\n"
        "    def get(self) -> User:\n        return User()\n",
    )
    _w(
        root,
        "src/shop/service.py",
        "from shop.repository import UserRepository\n\n\n"
        "def make_service() -> UserRepository:\n    return UserRepository()\n",
    )
    _w(
        root,
        "tests/test_models.py",
        "from shop.models import User\n\n\ndef test_user():\n    assert User\n",
    )
    return root


def default_cases() -> list[EvalCase]:
    """Questions a cold agent would ask, with independently-known answers."""

    def language(root: Path) -> tuple[bool, str]:
        got = tools.get_project_summary(root)["fingerprint"].get("language")
        return got == "Python", f"language={got!r} (expected Python)"

    def framework(root: Path) -> tuple[bool, str]:
        got = tools.get_project_summary(root)["fingerprint"].get("framework")
        return got == "FastAPI", f"framework={got!r} (expected FastAPI)"

    def dependency(root: Path) -> tuple[bool, str]:
        names = {d["name"] for d in tools.get_dependencies(root)["dependencies"]}
        return "fastapi" in names, f"deps={sorted(names)}"

    def critical(root: Path) -> tuple[bool, str]:
        files = tools.get_critical_files(root)["critical_files"]
        top = files[0]["path"] if files else None
        return top == "src/shop/models.py", f"top critical={top}"

    def where_defined(root: Path) -> tuple[bool, str]:
        res = tools.find_symbol(root, "make_service")
        path = res["definitions"][0]["path"] if res["found"] else None
        return path == "src/shop/service.py", f"defined at {path}"

    def which_tests(root: Path) -> tuple[bool, str]:
        paths = {t["path"] for t in tools.what_tests(root, "models.py")["tests"]}
        return "tests/test_models.py" in paths, f"tests={sorted(paths)}"

    def impact_not_isolated(root: Path) -> tuple[bool, str]:
        report = tools.analyze_impact(root, "models.py")
        affected = report.get("affected_file_count", 0)
        return affected > 0, f"models.py affected_file_count={affected} (expected >0)"

    def trustworthy(root: Path) -> tuple[bool, str]:
        conf = tools.get_health(root)["confidence"]
        return conf in {"high", "medium"}, f"confidence={conf}"

    return [
        EvalCase("language", "What language is this repo?", language),
        EvalCase("framework", "What framework does it use?", framework),
        EvalCase("dependency", "Does it depend on fastapi?", dependency),
        EvalCase("critical_file", "What is the most depended-on file?", critical),
        EvalCase("find_symbol", "Where is make_service defined?", where_defined),
        EvalCase("what_tests", "Which tests cover models.py?", which_tests),
        EvalCase("impact", "Is changing models.py isolated?", impact_not_isolated),
        EvalCase("trust", "Is the graph trustworthy (imports resolved)?", trustworthy),
    ]


def run_eval(root: Path, cases: list[EvalCase] | None = None) -> EvalReport:
    """Build memory for ``root`` and grade every case, plus token accounting."""
    from repointel.context.compression import context_pack
    from repointel.context.memory import build_memory, persist_memory
    from repointel.storage.json import read_repo_summary, read_repository

    root = Path(root)
    if read_repo_summary(root) is None:
        persist_memory(build_memory(root), root)
    cases = cases if cases is not None else default_cases()

    results: list[EvalResult] = []
    for case in cases:
        try:
            passed, detail = case.check(root)
        except Exception as exc:  # a crash is a failed answer, not a crashed eval
            passed, detail = False, f"error: {exc}"
        results.append(EvalResult(case.name, case.question, passed, detail))

    pack = context_pack(root)
    context_tokens = estimate_tokens(render_context_markdown(pack)) if pack else 0
    raw_tokens = _raw_source_tokens(root, read_repository(root))
    return EvalReport(
        total=len(results),
        passed=sum(r.passed for r in results),
        results=results,
        context_tokens=context_tokens,
        raw_tokens=raw_tokens,
    )


def _raw_source_tokens(root: Path, inventory) -> int:
    if inventory is None:
        return 0
    chars = 0
    for entry in inventory.files:
        if entry.language:
            try:
                chars += (Path(inventory.path) / entry.path).stat().st_size
            except OSError:
                continue
    return chars // 4  # ~4 chars/token


__all__ = [
    "EvalCase",
    "EvalReport",
    "EvalResult",
    "build_reference_repo",
    "default_cases",
    "run_eval",
]
