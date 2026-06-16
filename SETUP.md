# Setup Guide

Everything a new developer needs to clone, install, and run RepoIntel — locally,
globally, in a container, and as an MCP server for AI agents.

> **TL;DR (easiest path):** install [uv], clone the repo, then
> `uv tool install .` → the `repointel` command works in every project on your
> machine. Jump to [Option B](#option-b--global-install-easiest-for-everyday-use).

[uv]: https://docs.astral.sh/uv/

---

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **Python 3.12+** | runtime | uv installs/manages it for you |
| **uv** | dependency & tool manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (macOS/Linux) — see [docs](https://docs.astral.sh/uv/getting-started/installation/) |
| **git** | clone the repo | preinstalled on most systems |
| **Docker** | *only* for the container option | [docker.com](https://docs.docker.com/get-docker/) |

Verify uv:

```bash
uv --version
```

## 1. Clone

```bash
git clone https://github.com/sadiqueiqbal0786/Repository-Intelligence-Layer-for-AI-Agents.git
cd Repository-Intelligence-Layer-for-AI-Agents
```

## 2. Choose how to install

| Option | Best for | You run it as |
|--------|----------|---------------|
| **A. Local** | contributing / hacking on RepoIntel | `uv run repointel …` |
| **B. Global** | using it day-to-day on other projects | `repointel …` (anywhere) |
| **C. Container** | isolation from your host Python | `docker run … repointel …` |

You can do more than one. Pick based on the table, then follow that section.

---

## Option A — Local (best for contributors)

Installs everything into a project-local virtual environment (`.venv/`):

```bash
uv sync            # create .venv and install deps + repointel (editable)
uv run repointel --help
uv run pytest      # run the test suite (should be all green)
```

Run any command with the `uv run` prefix:

```bash
uv run repointel analyze .
uv run repointel build .
uv run repointel context .
```

Nothing is installed system-wide; delete `.venv/` to remove it.

---

## Option B — Global install (easiest for everyday use)

Installs `repointel` as a standalone command available in **every** directory:

```bash
uv tool install .          # run from inside the cloned repo
repointel --version        # confirm it's on your PATH
```

If `repointel` is "command not found" right after install, your shell's PATH
needs the uv tool bin dir:

```bash
uv tool update-shell       # then restart your terminal
```

Now use it anywhere — no `uv run` prefix:

```bash
cd /path/to/any/project
repointel analyze .
repointel build .
repointel context .
```

**Update** after pulling new changes: `uv tool install . --force`
**Remove**: `uv tool uninstall repointel`

> Prefer pipx? `pipx install .` works the same way.

---

## Option C — Container (isolation from host Python)

Build the image once (a [`Dockerfile`](Dockerfile) ships with the repo):

```bash
docker build -t repointel .
```

Run a command against any repo by bind-mounting it (RepoIntel writes
`.repointel/` back into the mount, so it must be read-write):

```bash
docker run --rm -v /absolute/path/to/project:/repo repointel build /repo
docker run --rm -v /absolute/path/to/project:/repo repointel context /repo
```

To run it as an MCP server from a container, see the container example in
[step 4](#4-use-it-as-an-mcp-server) (note the `-i` flag for stdio).

---

## 3. First run — confirm it works

From any project directory (adjust the `repointel` / `uv run repointel` prefix
to your option):

```bash
repointel analyze .     # detects language, framework, etc.
repointel build .       # writes .repointel/ memory artifacts
repointel context .     # prints the compact, agent-ready summary
```

If `context` prints a readable summary, you're set.

---

## 4. Use it as an MCP server

`repointel serve <path>` is a standard **stdio MCP server**. Your AI agent spawns
it automatically; you just add a config entry. Pick the `command`/`args` that
match how you installed it:

| Install | `command` | `args` |
|---------|-----------|--------|
| Global (B) | `repointel` | `["serve", "/abs/path/to/project"]` |
| Local (A) | `uv` | `["run", "--directory", "/abs/path/to/repointel", "repointel", "serve", "/abs/path/to/project"]` |
| Container (C) | `docker` | `["run", "--rm", "-i", "-v", "/abs/path/to/project:/repo", "repointel", "serve", "/repo"]` |

Use **absolute paths**. The examples below use the global form — swap in your row.

### Claude Code

Create `.mcp.json` in the project root, then run `/mcp` inside Claude Code to
approve:

```json
{
  "mcpServers": {
    "repointel": { "command": "repointel", "args": ["serve", "/abs/path/to/project"] }
  }
}
```

Or from the CLI: `claude mcp add repointel -- repointel serve /abs/path/to/project`

### Claude Desktop

Settings → Developer → Edit Config (`claude_desktop_config.json`), add under
`mcpServers`, restart:

```json
{
  "mcpServers": {
    "repointel": { "command": "repointel", "args": ["serve", "/abs/path/to/project"] }
  }
}
```

### OpenAI Codex (CLI)

`~/.codex/config.toml`:

```toml
[mcp_servers.repointel]
command = "repointel"
args = ["serve", "/abs/path/to/project"]
```

### Gemini CLI

`~/.gemini/settings.json` (or project-level `.gemini/settings.json`):

```json
{
  "mcpServers": {
    "repointel": { "command": "repointel", "args": ["serve", "/abs/path/to/project"] }
  }
}
```

### Any other MCP client

Configure a **stdio** server with the `command`/`args` from the table above.

### Adding alongside an existing MCP server

MCP configs hold a **map of servers keyed by name**, so adding RepoIntel never
replaces what's already there — you add a `repointel` entry next to the others.
The one rule: **merge, don't overwrite**, and keep names unique.

JSON clients (Claude Code, Claude Desktop, Gemini) — add the key inside the
existing `mcpServers` object:

```json
{
  "mcpServers": {
    "existing-server": { "command": "...", "args": ["..."] },
    "repointel": { "command": "repointel", "args": ["serve", "/abs/path/to/project"] }
  }
}
```

Codex (TOML) — add another table; existing ones stay:

```toml
[mcp_servers.existing_server]
command = "..."

[mcp_servers.repointel]
command = "repointel"
args = ["serve", "/abs/path/to/project"]
```

**Safest for Claude Code** — let the CLI merge it for you (it appends, never
touches existing servers):

```bash
claude mcp add repointel -- repointel serve /abs/path/to/project
```

The agent then lists **both** servers; their tools coexist (RepoIntel's are
namespaced, so no clashes). The only thing to avoid is a duplicate server *name*
— if something is already called `repointel`, rename one.

### Verify the connection

In your agent, list MCP servers (e.g. `/mcp` in Claude Code) — `repointel`
should show **connected** with **10 tools**. Then ask:

> Use the repointel `get_context` tool to summarize this repository.

The first call builds `.repointel/` (a few seconds), then reuses it.

---

## 5. Keeping the memory fresh

Memory is a snapshot. After code changes, refresh it (incremental — only
re-reads changed files):

```bash
repointel update .
```

To automate it, add a `Stop` hook in `.claude/settings.json` that runs
`repointel update .` after each turn (see this repo's `.claude/settings.json`
for a working example), or a git `post-commit` hook.

---

## 6. Uninstall / clean up

| What | How |
|------|-----|
| Local venv | `rm -rf .venv` |
| Global tool | `uv tool uninstall repointel` |
| Container image | `docker rmi repointel` |
| Generated memory | `rm -rf .repointel` (in the analyzed project) |
| Running MCP servers | `pkill -f "repointel serve"` |

---

## 7. Troubleshooting

**`uv: command not found`** — install uv (see Prerequisites) and restart your
shell.

**`repointel: command not found` after global install** — run
`uv tool update-shell`, then open a new terminal.

**MCP server shows "failed" / won't connect** — almost always a path issue:
- Use an **absolute** path in `args`.
- For the local option, make sure `--directory` points at the **RepoIntel repo**
  and the `serve` path points at the **target project**.
- Test the exact command in a terminal first, e.g. `repointel serve /abs/path`
  (you should see a `RepoIntel MCP server · …` banner on stderr; Ctrl+C to stop).
- Run the agent with debug logging (e.g. `claude --debug`) to see the spawn error.

**Wrong Python version** — you don't need to manage it; `uv sync` / `uv tool
install` provision Python 3.12 automatically.

**Tests fail right after clone** — ensure `uv sync` completed, then
`uv run pytest -q`. Open an issue with the output if they still fail.
