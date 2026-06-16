# RepoIntel

> Repository Intelligence Layer for AI Agents

**Build repository understanding once. Let every AI agent reuse it.**

RepoIntel analyzes source code and creates a persistent, machine-readable
**repository memory** — architecture, dependencies, conventions, relationships,
and change impact. Instead of every AI agent rediscovering your codebase from
scratch, they consume RepoIntel's memory and become productive immediately.

```text
Repository
     ↓
RepoIntel
     ↓
Repository Memory (.repointel/)
     ↓
MCP Server
     ↓
AI Agents / Developers / CI
```

> **Pre-alpha (v0.0.1).** Every phase below is implemented and covered by the
> test suite (89 passing tests), but interfaces may still change.

---

## Why?

Every AI coding agent starts a session by exploring:

- README files
- Project structure
- Dependencies
- Architecture
- Coding conventions

This process is repeated **every session, every model, every agent**. The result:

- ❌ Wasted tokens
- ❌ Slower execution
- ❌ Inconsistent understanding
- ❌ Poorer architectural decisions

RepoIntel solves this by creating a persistent repository memory layer that
agents can load instantly.

## Before / After

**Before RepoIntel**

```text
Agent
  ↓ read README
  ↓ explore folders
  ↓ open dozens of files
  ↓ infer architecture
  ↓ start working

Time: minutes · Tokens: thousands
```

**After RepoIntel**

```text
Agent
  ↓ load RepoIntel memory
  ↓ understand architecture
  ↓ start working

Time: seconds · Tokens: hundreds
```

## Benchmark

Measured on this repository with `repointel benchmark .`:

| | Tokens |
|--|--|
| Raw source | **~56,000** |
| RepoIntel context pack | **~290** |
| **Reduction** | **≈190×** |

The ~290-token pack still conveys identity, layers, key files, conventions,
dependencies, recorded decisions, and history — enough for an agent to start
working immediately.

## Features

- 🔎 Repository fingerprinting (language, framework, build system)
- 📦 Dependency & inventory analysis
- 🕸️ Architecture graph generation (imports / calls / inheritance)
- 🧠 Persistent repository memory (`.repointel/`)
- 🔌 MCP integration (10 tools, any MCP agent)
- 📐 Convention discovery (naming, DI, layering, patterns)
- 💥 Change-impact analysis (blast radius before you edit)
- 🗂️ Explanation engine (purpose / consumers / risk, no LLM)
- 📚 Knowledge layer (architecture decisions + git history)
- ⚡ Incremental updates (re-analyze only what changed)
- 🧩 Multi-language plugin system (add languages, no core edits)
- 🪶 Context-pack compression (~190× smaller than source)

## Quick Start

Requires **Python 3.12+** and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                        # install into a managed virtualenv
uv run repointel analyze .     # what kind of project is this?
uv run repointel build .       # build the full repository memory → .repointel/
uv run repointel context .     # the compact, agent-ready understanding
```

> 📘 **New here?** [**SETUP.md**](SETUP.md) is a full step-by-step guide —
> local, global (`repointel` everywhere), container, and MCP-server setup for
> Claude / Codex / Gemini.

That's the core loop. The full CLI:

```bash
uv run repointel scan .        # full inventory
uv run repointel graph .       # architecture graph
uv run repointel update .      # incremental refresh (only changed files)
uv run repointel explain auth  # explain a module: purpose, consumers, risk
uv run repointel impact base.py# predict the blast radius of changing a file
uv run repointel knowledge .   # decisions, patterns, project history
uv run repointel decide "Use uv" --why "fast, reproducible installs"
uv run repointel benchmark .   # raw-vs-pack token savings
uv run repointel serve .       # run the MCP server for AI agents
uv run pytest                  # run the tests
```

## Repository Memory

`repointel build .` writes the canonical memory set agents load without
rescanning:

```text
.repointel/
├── repo.json          # compact overview + manifest (fingerprint, counts, entry points)
├── repository.json    # full file / module / dependency inventory
├── graph.json         # architecture graph: nodes + edges
├── architecture.json  # style, layers, languages, frameworks, key files
├── modules.json       # per-module files, LOC, class/function counts, imports
├── conventions.json   # naming, layout, dependency injection, patterns, testing
└── knowledge.json     # architecture decisions, inferred patterns, git history
```

| File | What it answers |
|------|-----------------|
| `repo.json` | What is this project, at a glance? |
| `repository.json` | What files, modules, and dependencies exist? |
| `graph.json` | What is connected to what? |
| `architecture.json` | What is the system's shape and where are the hubs? |
| `modules.json` | What does each module contain and import? |
| `conventions.json` | How does this team write code? |
| `knowledge.json` | Why is it built this way, and how has it evolved? |

(An internal `cache.json` also lives here to power incremental updates; it is not
part of the agent-facing memory.)

## Who Is This For?

**AI agents** — Claude Code, Codex, Gemini, Cline, Roo Code, and any MCP client.
Load the whole repo's understanding in one `get_context` call.

**Developers** — faster onboarding, instant architecture overviews, and
impact analysis before refactors.

**Teams** — a shared repository memory and preserved architectural decisions
that travel with the code.

**CI/CD systems** — fast structural analysis and automated architecture checks.

## Connecting AI agents (MCP)

`repointel serve <path>` is a standard **stdio MCP server**. Once connected, an
agent has these tools (start with **`get_context`**): `get_context`,
`get_project_summary`, `get_architecture`, `get_conventions`, `get_knowledge`,
`get_module_info`, `get_dependencies`, `get_critical_files`, `explain_module`,
`analyze_impact`. Memory is built on the first call and reused afterward.

In normal use your agent spawns the server and shuts it down automatically. To
run it by hand for a smoke test: `uv run repointel serve /path/to/repo`
(`Ctrl+C` to stop; background processes: `pkill -f "repointel serve"`).

Use an **absolute path** for the repo in each config below.

<details>
<summary><b>Claude Code</b></summary>

Project-scoped — create `.mcp.json` in the repo root, then run `/mcp` to approve:

```json
{
  "mcpServers": {
    "repointel": { "command": "uv", "args": ["run", "repointel", "serve", "/path/to/your/repo"] }
  }
}
```

Or: `claude mcp add repointel -- uv run repointel serve /path/to/your/repo`
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config (`claude_desktop_config.json`), add under
`mcpServers`, then restart:

```json
{
  "mcpServers": {
    "repointel": { "command": "uv", "args": ["run", "repointel", "serve", "/path/to/your/repo"] }
  }
}
```
</details>

<details>
<summary><b>OpenAI Codex (CLI)</b></summary>

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.repointel]
command = "uv"
args = ["run", "repointel", "serve", "/path/to/your/repo"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add to `~/.gemini/settings.json` (or a project-level `.gemini/settings.json`):

```json
{
  "mcpServers": {
    "repointel": { "command": "uv", "args": ["run", "repointel", "serve", "/path/to/your/repo"] }
  }
}
```
</details>

<details>
<summary><b>Any other MCP client / Docker</b></summary>

Configure a stdio server with command `uv`, args
`["run", "repointel", "serve", "/path/to/your/repo"]`. If `repointel` is on the
PATH (`uv tool install .`), drop `uv run`.

In a container (note `-i` for stdio):

```json
{
  "mcpServers": {
    "repointel": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "/path/to/your/repo:/repo", "repointel", "serve", "/repo"]
    }
  }
}
```

Build the image first: `docker build -t repointel .` (see the [`Dockerfile`](Dockerfile)).
</details>

## Current Status

RepoIntel is built out through all 12 development phases — each row below is
implemented and tested.

| Phase | Feature | Status |
|------:|---------|:------:|
| 0 | Foundation | ✅ |
| 1 | Fingerprinting | ✅ |
| 2 | Scanner | ✅ |
| 3 | Graph Engine | ✅ |
| 4 | Repository Memory | ✅ |
| 5 | MCP Server | ✅ |
| 6 | Convention Discovery | ✅ |
| 7 | Incremental Intelligence | ✅ |
| 8 | Explanation Engine | ✅ |
| 9 | Change Impact Analysis | ✅ |
| 10 | Plugin Ecosystem | ✅ |
| 11 | Knowledge Layer | ✅ |
| 12 | Repository Intelligence Platform | ✅ |

First analyzer targets: **Python** and **Flutter/Dart**. New languages are added
as plugins — see the [plugin authoring guide](docs/plugins.md).

## Project layout

Clean-architecture layout — inner layers (`models`) know nothing about outer
layers (`cli`, `mcp`):

```text
src/repointel/
├── cli/         # Typer app + commands/
├── scanners/    # Per-language ecosystem detection
├── graph/       # Architecture graph: builder/ traversal/ impact/
├── context/     # Understanding: conventions, explanation, knowledge, compression
├── plugins/     # Multi-language plugin registry + built-ins
├── storage/     # Persistence (.repointel/ JSON)
├── mcp/         # MCP server + tools
└── models/      # Domain entities
```

## Contributing

Contributions and ideas are welcome. Get your environment running with
[SETUP.md](SETUP.md), then — adding a language is as simple as shipping a plugin
(no core changes) — start with [docs/plugins.md](docs/plugins.md).

## Author

**Sadique Iqbal** — AI and mobile app developer.
📧 [sadiqueiqbal.si@gmail.com](mailto:sadiqueiqbal.si@gmail.com)

## License

[Apache-2.0](LICENSE)

## Vision

Git became the source of truth for code.

**RepoIntel aims to become the source of truth for repository _understanding_.**

> Analyze once. Understand forever.
> Let every AI agent reuse the same repository intelligence.
