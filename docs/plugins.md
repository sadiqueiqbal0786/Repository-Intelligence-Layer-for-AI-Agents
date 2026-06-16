# Writing a RepoIntel language plugin (Phase 10)

RepoIntel supports new languages through **plugins** — self-contained packages
that the core discovers at runtime. Adding a language never requires editing a
core file.

A plugin bundles up to two extension points behind one object:

| Part | Interface | Responsibility |
|------|-----------|----------------|
| **Scanner** | `repointel.scanners.base.Scanner` | Ecosystem detection: fingerprint (framework, package manager, databases), dependencies, entry points. |
| **Parser** | `repointel.plugins.Parser` | Turn source text into the graph IR (`ParsedFile`: imports, classes, functions). |

Either may be `None`. A *parser-only* plugin graphs a language whose ecosystem
the core already covers; a *scanner-only* plugin recognizes an ecosystem it
doesn't yet graph.

## The `Parser` contract

```python
class Parser(Protocol):
    language: str  # canonical name, matching the core CODE_EXTENSIONS table (e.g. "Go")

    def make_resolver(self, files: set[str], root: Path) -> object:
        """Build a per-build import resolver (the parser owns its type)."""

    def parse(self, path: str, source: str, resolver: object) -> ParsedFile | None:
        """Parse one file into the IR; return None if it can't be parsed."""
```

`language` must match the name the core assigns to the file extension (see
`CODE_EXTENSIONS` in `repointel.scanners.base`). Most mainstream languages — Go,
Rust, Java, TypeScript, C/C++, Ruby, … — are **already** recognized there, so a
parser is all you need. A brand-new extension is the one case that still needs a
core addition.

## A minimal plugin

```python
from repointel.graph.builder.parsed import ParsedClass, ParsedFile, ParsedFunction
from repointel.plugins import Plugin

class GoParser:
    language = "Go"
    def make_resolver(self, files, root):
        return files
    def parse(self, path, source, resolver):
        pf = ParsedFile(path=path, language="Go")
        # ... extract structs -> pf.classes, funcs -> pf.functions ...
        return pf

go_plugin = Plugin(name="go", parser=GoParser())
```

See [`plugins/go/`](../plugins/go/) for the full worked example.

## Registering a plugin

**Packaged (recommended).** Advertise an entry point in the
`repointel.plugins` group; installing the package is enough:

```toml
[project.entry-points."repointel.plugins"]
go = "repointel_go:go_plugin"
```

The value resolves to a `LanguagePlugin`, or to a zero-arg callable that returns
one. A plugin that fails to import or load is skipped — it never breaks the core.

**In-process.** For scripts and tests, register directly:

```python
from repointel.plugins import register_plugin
register_plugin(go_plugin)
```

Built-in plugins (Python, Dart) take priority on ties; the most recently
registered third-party plugin wins over earlier ones for the same language.
