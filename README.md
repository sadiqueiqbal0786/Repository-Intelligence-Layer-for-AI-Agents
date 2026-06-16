# RepoIntel

**Repository Intelligence Engine** — a persistent, machine-readable memory layer
for codebases that AI agents can consume.

RepoIntel continuously analyzes a repository and builds a machine-readable
understanding of its architecture, dependencies, conventions, relationships, and
change impact. The goal is not documentation: it's a **persistent repository
memory layer** that any AI agent can load in seconds instead of spending
thousands of tokens exploring files.

```text
Repository → RepoIntel Scanner → Repository Memory → Architecture Graph → MCP Server → AI Agents / Developers / CI
```

## Status

🚧 **Phase 4 — Repository Memory.** `repointel build .` runs the full pipeline
(fingerprint → inventory → graph → derived summaries) and writes the canonical
`.repointel/` memory set — the source of truth an agent loads without
rescanning:

| File | Contents |
|------|----------|
| `repo.json` | compact overview + manifest (fingerprint, counts, entry points) |
| `repository.json` | full file/module/dependency inventory (Phase 2) |
| `graph.json` | architecture graph: nodes + edges (Phase 3) |
| `architecture.json` | style, layers, languages, frameworks, key (most-imported) files |
| `modules.json` | per-module files, LOC, class/function counts, inter-module imports |
| `conventions.json` | source layout, package manager, file naming, testing setup |

Python is parsed via the `ast` module; Dart via regex. TypeScript and Java are
scaffolded as stubs. The MCP server (Phase 5) is next.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Quickstart

```bash
# Install dependencies into a managed virtual environment
uv sync

# Run the CLI
uv run repointel --help
uv run repointel --version
uv run repointel analyze .          # Phase 1: fingerprint
uv run repointel scan .             # Phase 2: full inventory → .repointel/repository.json
uv run repointel scan . --json      # emit the inventory as JSON
uv run repointel graph .            # Phase 3: architecture graph → .repointel/graph.json
uv run repointel build .            # Phase 4: full repository memory → .repointel/

# Run the tests
uv run pytest
```

## Project layout

The engine follows a clean-architecture layout — inner layers (`models`) know
nothing about outer layers (`cli`, `mcp`):

```text
src/repointel/
├── cli/            # Delivery: Typer app + commands/
├── scanners/       # Per-language analysis: python/ dart/ typescript/ java/
├── graph/          # Architecture graph: builder/ traversal/ impact/   (Phase 3+)
├── context/        # Understanding: architecture/ summary/ compression/
├── storage/        # Persistence: json/ sqlite/                        (Phase 4+)
├── mcp/            # MCP server for AI agents                          (Phase 5)
└── models/         # Domain entities (Fingerprint, ...)
```

Supporting top-level dirs: `tests/`, `docs/`, `examples/`, `plugins/`,
`.github/workflows/`.

## Roadmap

| Phase | Title | Status |
|------:|-------|--------|
| 0 | Project Foundation | ✅ done |
| 1 | Repository Fingerprinting | ✅ Python + Flutter/Dart |
| 2 | Repository Scanner | ✅ inventory → `.repointel/repository.json` |
| 3 | Architecture Graph Engine | ✅ graph → `.repointel/graph.json` |
| 4 | Repository Memory | ✅ `repointel build` → full `.repointel/` set |
| 5 | MCP Server | ⬜ |
| 6 | Convention Discovery | ⬜ |
| 7 | Incremental Intelligence | ⬜ |
| 8 | Explanation Engine | ⬜ |
| 9 | Change Impact Analysis | ⬜ |
| 10 | Multi-Language Plugin Ecosystem | ⬜ |
| 11 | Knowledge Layer | ⬜ |
| 12 | Repository Intelligence Platform | ⬜ |

First analyzer targets: **Python** and **Flutter/Dart**.

## License

Apache-2.0
