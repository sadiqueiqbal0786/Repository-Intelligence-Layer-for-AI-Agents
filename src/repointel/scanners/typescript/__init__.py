"""TypeScript / JavaScript ecosystem scanner (placeholder).

Planned signal: package.json (npm/pnpm/yarn/bun), Next.js / React / NestJS,
Prisma / Drizzle, tsconfig.json. Implement ``matches``/``fingerprint`` and add
to the registry in :mod:`repointel.scanners` when ready.
"""

from __future__ import annotations

from repointel.models import Dependency, Fingerprint
from repointel.scanners.base import RepoContext


class TypeScriptScanner:
    name = "typescript"

    def matches(self, ctx: RepoContext) -> bool:
        return False  # not implemented yet

    def fingerprint(self, ctx: RepoContext, fp: Fingerprint) -> None:  # pragma: no cover
        raise NotImplementedError

    def dependencies(self, ctx: RepoContext) -> list[Dependency]:  # pragma: no cover
        return []

    def entry_points(self, ctx: RepoContext) -> list[str]:  # pragma: no cover
        return []
