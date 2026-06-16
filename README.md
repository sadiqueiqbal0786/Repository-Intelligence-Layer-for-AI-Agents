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

> On this repository, `repointel benchmark .` represents **~56k tokens of source
> in a ~290-token context pack — roughly 190× compression**. Run it on yours.

## Purpose

Every time an AI agent opens an unfamiliar repository, it re-discovers the same
things — the framework, the layout, the conventions, what depends on what —
burning thousands of tokens and minutes of wall-clock before it can do useful
work. And every new agent (or teammate) starts from zero.

RepoIntel removes that tax. **Analyze a repository once**, and it produces a
persistent, machine-readable memory layer (`.repointel/`) that any agent can load
in seconds. It sits *between your source code and your AI agents* as a shared
understanding they all consume.

**Use it to:**

- **Onboard an agent instantly** — `get_context` hands over a whole repo's shape
  (identity, layers, key files, conventions, dependencies, decisions, history)
  in a few hundred tokens instead of a file-by-file crawl.
- **Generate code that fits** — agents follow the repo's *actual* naming,
  architecture, DI, and testing conventions (Phase 6), not generic defaults.
- **Check blast radius before a change** — `impact <file>` predicts what a
  refactor touches *before* you touch it (Phase 9).
- **Answer architecture questions** — `explain <module>` describes purpose,
  consumers, and risk with no LLM call (Phase 8).
- **Preserve the *why*** — record architecture decisions that survive rebuilds
  and travel with the repo (Phase 11).

**Who it's for:** AI coding agents (Claude, Codex, Gemini, …), developers
onboarding to a new codebase, and CI systems that need a fast structural read.

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
| `conventions.json` | naming (files/classes/functions), source layout, dependency injection, layering, patterns, testing setup |
| `knowledge.json` | architecture decisions (ADRs + recorded), inferred patterns, git history — the durable knowledge layer |

Python is parsed via the `ast` module; Dart via regex. Both ship as built-in
plugins (see Phase 10); TypeScript and Java are scaffolded as scanner stubs, and
new languages can be added as plugins without touching the core.

🚧 **Phase 5 — MCP Server.** `repointel serve .` runs an MCP server (stdio) that
exposes the memory layer to AI agents via ten tools: `get_context`,
`get_project_summary`, `get_architecture`, `get_conventions`, `get_knowledge`,
`get_module_info`, `get_dependencies`, `get_critical_files`, `explain_module`,
and `analyze_impact`. Memory is built automatically on first request.

🚧 **Phase 6 — Convention Discovery.** `conventions.json` is deepened so agents
write code the way the team already does: identifier-casing for classes and
functions is inferred from the graph, the dependency-injection / wiring
framework is detected from dependencies, and recurring layer directories (e.g.
`domain`/`data`/`presentation`) and the structural patterns they imply
(`repository_pattern`, `service_layer`, …) are surfaced. Exposed over MCP via
`get_conventions`.

🚧 **Phase 7 — Incremental Intelligence.** `repointel update .` refreshes memory
by re-reading and re-parsing only the source files whose `(size, mtime)`
signature changed since the last build — everything else is reused from
`.repointel/cache.json`. Pure edits to existing files take a fast path that
reuses cached parsed IR; adding or deleting a parseable file falls back to a
full parse (still correct). The result is always identical to a from-scratch
`build`. `cache.json` is an internal optimization and is not part of the
agent-facing manifest.

🚧 **Phase 8 — Explanation Engine.** `repointel explain <module>` generates a
structured, **LLM-free** explanation straight from memory: a purpose sentence
(inferred from structure + naming conventions), what the module depends on, who
depends on it, its most-critical files, its blast radius (transitive
dependents), and a derived risk level for changing it. Exposed over MCP via
`explain_module`.

🚧 **Phase 9 — Change Impact Analysis.** `repointel impact <file>` predicts the
consequences of editing a file *before* you touch it: it walks `imports` edges
backwards to find every file that transitively depends on it (the blast radius),
the modules they span, what the file itself depends on, and a risk level. Useful
right before a refactor. Exposed over MCP via `analyze_impact`.

🚧 **Phase 10 — Multi-Language Plugin Ecosystem.** Language support is now a
plugin: a `LanguagePlugin` bundles a `Scanner` (ecosystem detection) and a
`Parser` (source → graph IR), and the scanners and graph builder dispatch
through a registry instead of hardcoded branches. Third-party packages register
via the `repointel.plugins` entry-point group — installing one teaches RepoIntel
a new language with **no core changes**. See the [authoring guide](docs/plugins.md)
and the worked [Go example](plugins/go/).

🚧 **Phase 11 — Knowledge Layer.** `knowledge.json` gives the repository
long-term memory beyond structure: **decisions** (discovered from ADR markdown
files, plus ones you record with `repointel decide "…" --why "…"`),
**patterns** (inferred from the conventions and architecture), and **history**
(commits, contributors, timeline from git). Recorded decisions are durable —
they survive every rebuild. View it with `repointel knowledge .`; exposed over
MCP via `get_knowledge`.

🚧 **Phase 12 — Repository Intelligence Platform.** The payoff: `repointel
context .` emits a **context pack** — a whole repository's understanding
(identity, key files, layers, conventions, dependencies, decisions, history) in
a few thousand tokens, the most token-efficient way for an agent to get oriented.
`repointel benchmark .` measures the win against reading raw source. On this
repository the pack represents **~56k tokens of source in ~290 tokens — a ~190×
compression**. Exposed over MCP via `get_context` (the recommended starting
tool).

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
uv run repointel update .           # Phase 7: refresh memory, re-analyzing only changed files
uv run repointel explain auth       # Phase 8: explain a module (purpose, consumers, risk)
uv run repointel impact base.py     # Phase 9: predict the blast radius of changing a file
uv run repointel knowledge .        # Phase 11: decisions, patterns, and project history
uv run repointel decide "Use uv"    # Phase 11: record an architecture decision (--why ...)
uv run repointel context .          # Phase 12: compact context pack (pipe into an agent)
uv run repointel benchmark .        # Phase 12: measure raw-vs-pack token savings
uv run repointel serve .            # Phase 5: run the MCP server (stdio) for AI agents

# Run the tests
uv run pytest
```

## Running the MCP server

`repointel serve <path>` starts an MCP server that speaks the protocol over
**stdio** — stdout carries the MCP messages, stderr carries status logs:

```bash
uv run repointel serve /path/to/your/repo
```

In normal use you don't run this by hand: your AI agent (the MCP *client*)
spawns the process when it connects and shuts it down when it disconnects — see
[Connecting AI agents](#connecting-ai-agents). Running it manually is useful only
to smoke-test that it starts — you'll see a `RepoIntel MCP server · <path>`
banner on stderr, and with no client attached it just waits for input.

Memory is built automatically on the first tool call and reused afterward.

### Stopping the server

- **Foreground:** press `Ctrl+C`.
- **Spawned by an agent:** it stops automatically when the agent disconnects —
  nothing to do.
- **Background / stuck process:** `pkill -f "repointel serve"`, or find the PID
  with `ps aux | grep "repointel serve"` and `kill <pid>`.

## Connecting AI agents

The server is a standard stdio MCP server, so any MCP-capable agent can use it.
Every config has the same shape — run `repointel serve` pointed at the repo you
want it to understand. Use an **absolute path** for `/path/to/your/repo`.

Once connected, the agent has these tools (start with **`get_context`**):
`get_context`, `get_project_summary`, `get_architecture`, `get_conventions`,
`get_knowledge`, `get_module_info`, `get_dependencies`, `get_critical_files`,
`explain_module`, `analyze_impact`.

### Claude Code

Project-scoped — create a `.mcp.json` in the repo root:

```json
{
  "mcpServers": {
    "repointel": {
      "command": "uv",
      "args": ["run", "repointel", "serve", "/path/to/your/repo"]
    }
  }
}
```

…or add it from the CLI:

```bash
claude mcp add repointel -- uv run repointel serve /path/to/your/repo
```

Then run `/mcp` inside Claude Code to approve and verify the connection.

### Claude Desktop

Open **Settings → Developer → Edit Config** (`claude_desktop_config.json`) and
add the server under `mcpServers`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "repointel": {
      "command": "uv",
      "args": ["run", "repointel", "serve", "/path/to/your/repo"]
    }
  }
}
```

### OpenAI Codex (Codex CLI)

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.repointel]
command = "uv"
args = ["run", "repointel", "serve", "/path/to/your/repo"]
```

### Gemini CLI

Add to `~/.gemini/settings.json` (or a project-level `.gemini/settings.json`):

```json
{
  "mcpServers": {
    "repointel": {
      "command": "uv",
      "args": ["run", "repointel", "serve", "/path/to/your/repo"]
    }
  }
}
```

### Any other MCP client

Configure a **stdio** server with command `uv` and args
`["run", "repointel", "serve", "/path/to/your/repo"]`. If `repointel` is
installed on the PATH (e.g. `uv tool install .` or `pipx install`), drop the
`uv run` wrapper: command `repointel`, args `["serve", "/path/to/your/repo"]`.

## Running in a container

A container isolates RepoIntel from your host Python. Build an image from this
repo:

```dockerfile
# Dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY . /app
RUN uv sync --frozen
ENTRYPOINT ["uv", "run", "repointel"]
```

```bash
docker build -t repointel .
```

Run one-off commands against a mounted repo (it writes `.repointel/` back into
the mount, so the bind must be read-write):

```bash
docker run --rm -v /path/to/your/repo:/repo repointel build /repo
docker run --rm -v /path/to/your/repo:/repo repointel context /repo
```

**As an MCP server inside a container**, the agent spawns `docker` — note the
`-i`, which keeps stdin open for the stdio stream:

```json
{
  "mcpServers": {
    "repointel": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/your/repo:/repo",
        "repointel", "serve", "/repo"
      ]
    }
  }
}
```

`--rm` removes the container on disconnect; `-i` is required for stdio.

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
| 5 | MCP Server | ✅ `repointel serve` — 10 MCP tools |
| 6 | Convention Discovery | ✅ `get_conventions` |
| 7 | Incremental Intelligence | ✅ `repointel update` |
| 8 | Explanation Engine | ✅ `repointel explain` |
| 9 | Change Impact Analysis | ✅ `repointel impact` |
| 10 | Multi-Language Plugin Ecosystem | ✅ entry-point plugins |
| 11 | Knowledge Layer | ✅ `repointel knowledge` / `decide` |
| 12 | Repository Intelligence Platform | ✅ `repointel context` / `benchmark` |

First analyzer targets: **Python** and **Flutter/Dart**.

## Author

**Sadique Iqbal** — AI and mobile app developer.

📧 [sadiqueiqbal.si@gmail.com](mailto:sadiqueiqbal.si@gmail.com)

Issues, ideas, and contributions are welcome.

## License

Apache-2.0
