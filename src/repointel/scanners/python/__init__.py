"""Python ecosystem scanner."""

from __future__ import annotations

import re
import tomllib

from repointel.models import Dependency, Fingerprint
from repointel.scanners.base import RepoContext

# Leading PEP 508 / requirements name, then anything after is treated as the spec.
_REQ_RE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*(.*)$")

# Entry-point filenames worth surfacing wherever they appear in the tree.
_ENTRY_FILENAMES = frozenset(
    {"main.py", "__main__.py", "manage.py", "app.py", "wsgi.py", "asgi.py"}
)

# dependency name (lowercased substring) -> framework label
_FRAMEWORKS: list[tuple[str, str]] = [
    ("fastapi", "FastAPI"),
    ("django", "Django"),
    ("flask", "Flask"),
    ("starlette", "Starlette"),
    ("sanic", "Sanic"),
    ("aiohttp", "aiohttp"),
    ("tornado", "Tornado"),
    ("litestar", "Litestar"),
]

_DATABASES: list[tuple[str, str]] = [
    ("sqlalchemy", "SQLAlchemy"),
    ("psycopg", "PostgreSQL"),
    ("asyncpg", "PostgreSQL"),
    ("pymongo", "MongoDB"),
    ("motor", "MongoDB"),
    ("redis", "Redis"),
    ("prisma", "Prisma"),
    ("tortoise-orm", "Tortoise ORM"),
    ("peewee", "Peewee"),
    ("sqlmodel", "SQLModel"),
    ("mysqlclient", "MySQL"),
    ("pymysql", "MySQL"),
]

_MARKERS = ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile")


class PythonScanner:
    name = "python"

    def matches(self, ctx: RepoContext) -> bool:
        return any(ctx.exists(m) for m in _MARKERS)

    def fingerprint(self, ctx: RepoContext, fp: Fingerprint) -> None:
        if fp.language is None:
            fp.set("language", "Python", "Python source files")

        self._package_manager(ctx, fp)
        self._build_system(ctx, fp)

        deps = self._dependency_blob(ctx)
        for needle, label in _FRAMEWORKS:
            if needle in deps and fp.framework is None:
                fp.set("framework", label, f"dependency '{needle}'")
                break

        seen: set[str] = set()
        for needle, label in _DATABASES:
            if needle in deps and label not in seen:
                seen.add(label)
                fp.databases.append(label)
        if fp.databases:
            fp.evidence["databases"] = "declared dependencies"

    def _package_manager(self, ctx: RepoContext, fp: Fingerprint) -> None:
        pyproject = ctx.read_text("pyproject.toml") or ""
        if ctx.exists("uv.lock"):
            fp.set("package_manager", "uv", "uv.lock")
        elif ctx.exists("poetry.lock") or "[tool.poetry]" in pyproject:
            fp.set("package_manager", "Poetry", "poetry.lock / [tool.poetry]")
        elif ctx.exists("pdm.lock") or "[tool.pdm]" in pyproject:
            fp.set("package_manager", "PDM", "pdm.lock / [tool.pdm]")
        elif ctx.exists("Pipfile"):
            fp.set("package_manager", "Pipenv", "Pipfile")
        elif ctx.exists("requirements.txt") or ctx.exists("setup.py"):
            fp.set("package_manager", "pip", "requirements.txt / setup.py")
        elif "[project]" in pyproject or "[build-system]" in pyproject:
            # PEP 621 project with no lockfile — pip is the safe default.
            fp.set("package_manager", "pip", "pyproject.toml (PEP 621)")

    def _build_system(self, ctx: RepoContext, fp: Fingerprint) -> None:
        raw = ctx.read_text("pyproject.toml")
        if not raw:
            return
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            return
        requires = data.get("build-system", {}).get("requires", [])
        blob = " ".join(requires).lower()
        for needle, label in (
            ("hatchling", "Hatchling"),
            ("poetry-core", "Poetry Core"),
            ("setuptools", "setuptools"),
            ("flit", "Flit"),
            ("pdm-backend", "PDM Backend"),
            ("maturin", "Maturin"),
        ):
            if needle in blob:
                fp.set("build_system", label, f"build-system requires '{needle}'")
                return

    def _dependency_blob(self, ctx: RepoContext) -> str:
        """Concatenate, lowercased, every place dependencies might be declared."""
        parts = [
            ctx.read_text("pyproject.toml"),
            ctx.read_text("requirements.txt"),
            ctx.read_text("Pipfile"),
            ctx.read_text("setup.py"),
            ctx.read_text("setup.cfg"),
        ]
        return "\n".join(p for p in parts if p).lower()

    # ---- Phase 2: inventory --------------------------------------------------

    def dependencies(self, ctx: RepoContext) -> list[Dependency]:
        deps: list[Dependency] = []
        deps.extend(self._pyproject_dependencies(ctx))
        if not deps:
            deps.extend(self._requirements_dependencies(ctx))
        return deps

    def entry_points(self, ctx: RepoContext) -> list[str]:
        found: list[str] = []

        # Declared console scripts in pyproject.
        data = self._pyproject_data(ctx)
        scripts = data.get("project", {}).get("scripts", {})
        for name, target in scripts.items():
            found.append(f"{name} = {target}")

        # Conventional runnable files.
        for rel, _size in ctx.files():
            if rel.rsplit("/", 1)[-1] in _ENTRY_FILENAMES:
                found.append(rel)
        return sorted(set(found))

    def _pyproject_data(self, ctx: RepoContext) -> dict:
        raw = ctx.read_text("pyproject.toml")
        if not raw:
            return {}
        try:
            return tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            return {}

    def _pyproject_dependencies(self, ctx: RepoContext) -> list[Dependency]:
        data = self._pyproject_data(ctx)
        if not data:
            return []
        deps: list[Dependency] = []
        project = data.get("project", {})

        for spec in project.get("dependencies", []):
            if dep := self._parse_requirement(spec, "pyproject.toml [project]"):
                deps.append(dep)

        for group, specs in project.get("optional-dependencies", {}).items():
            for spec in specs:
                if dep := self._parse_requirement(
                    spec, f"pyproject.toml [optional: {group}]", dev=True
                ):
                    deps.append(dep)

        for group, specs in data.get("dependency-groups", {}).items():
            source = f"pyproject.toml [group: {group}]"
            for spec in specs:
                if not isinstance(spec, str):
                    continue
                if dep := self._parse_requirement(spec, source, dev=True):
                    deps.append(dep)

        # Poetry-style table: {name: version-constraint}.
        poetry = data.get("tool", {}).get("poetry", {})
        for name, constraint in poetry.get("dependencies", {}).items():
            if name.lower() == "python":
                continue
            version = constraint if isinstance(constraint, str) else None
            deps.append(
                Dependency(name=name, version=version, source="pyproject.toml [tool.poetry]")
            )
        return deps

    def _requirements_dependencies(self, ctx: RepoContext) -> list[Dependency]:
        raw = ctx.read_text("requirements.txt")
        if not raw:
            return []
        deps: list[Dependency] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            if dep := self._parse_requirement(line, "requirements.txt"):
                deps.append(dep)
        return deps

    def _parse_requirement(self, spec: str, source: str, *, dev: bool = False) -> Dependency | None:
        match = _REQ_RE.match(spec)
        if not match:
            return None
        name = match.group(1)
        version = (match.group(3) or "").strip() or None
        return Dependency(name=name, version=version, source=source, dev=dev)
