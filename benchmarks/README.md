# RepoIntel benchmarks

The platform's core promise (Phase 12) is **token savings**: an AI agent that
loads RepoIntel's compact context pack understands a repository for a tiny
fraction of the tokens it would spend reading the source. This folder is where
we measure it.

## Run it

```bash
# the current repo
uv run repointel benchmark .

# several repositories at once
uv run repointel benchmark . /path/to/repo-a /path/to/repo-b

# machine-readable
uv run repointel benchmark . --json
```

Each row reports, per repository:

| Metric | Meaning |
|--------|---------|
| Files | Source files analyzed |
| LOC | Lines of source code |
| Raw tokens | Estimated tokens to read all source (~4 chars/token) |
| Pack tokens | Estimated tokens of the `context` pack an agent loads instead |
| Ratio | Raw ÷ pack — the compression factor |
| Time (s) | Wall-clock to analyze from scratch |

The pack itself is what an agent consumes — inspect it with:

```bash
uv run repointel context .            # markdown (pipe into a prompt)
uv run repointel context . --json     # structured
```

## Methodology & caveats

- Token counts are **estimates** (~4 characters per token). They're for
  *comparison*, not billing; the compression ratio is stable across tokenizers.
- "Raw tokens" assumes an agent reads every source file once — the realistic
  cost of understanding an unfamiliar repo without a memory layer. The pack
  replaces that with a single curated load.
- The pack deliberately omits the heavy raw layers (full inventory, graph,
  cache); it carries the *understanding*, not the data.

## Adding repositories

To benchmark a corpus, clone 5–10 real-world repositories of varying size and
ecosystem (Python, Dart/Flutter, and — via plugins — Go/Rust/etc.) somewhere
local, then point the command at them. Clones are intentionally **not** vendored
into this repo; pass their paths at run time.
