# epoCity

Turn a codebase into a city you can fly through — then send an agent to clean up the bad neighborhoods.

epoCity statically analyzes a repository, renders it as a 3D city where every building is a file,
and lets you point a local LLM at the ugly parts to propose refactorings. Buildings grow with lines
of code and rust over with cyclomatic complexity, so the parts of your codebase that need attention
are the ones you notice first.

> **Status: pre-alpha.** The design is settled and Phase 1 is being built. There is nothing to run
> yet. Watch [docs/ROADMAP.md](docs/ROADMAP.md) for what lands when.

## The idea

| You see | It means |
|---|---|
| A district | A directory |
| A building | A file |
| Building height | Lines of code |
| Rusted concrete, red glow, smoke | High cyclomatic complexity |
| Clean glass, blue neon | Low complexity |
| Glowing arcs between buildings | Imports |
| A thick red tangle | A circular dependency |

Click a building to inspect its metrics and source. Type a command — *"split the most complex
function in this file"* — and an agent reads the file plus its direct dependencies, proposes a diff,
and shows it to you. Accept it, and the building collapses and rebuilds itself into whatever the
refactoring produced.

## How it works

```
apps/web            React Three Fiber canvas + Monaco inspector + command bar
services/analyzer   Python: tree-sitter parsing, metrics, import graph, treemap layout
                    FastAPI REST + WebSocket, agent runtime
LLM                 Any OpenAI-compatible endpoint (vLLM, Ollama, LM Studio)
```

The analyzer produces a `CityMap.json` — a stable, deterministic description of the city. Stable
IDs are what make the refactoring animation meaningful: when a file changes, only that building
changes, and the rest of the city stays exactly where you left it.

Design decisions and their rationale live in [docs/DESIGN.md](docs/DESIGN.md) (Korean).

## Safety

The agent never writes to your files on its own. It produces a unified diff, verifies the result
still parses, and shows it to you. Files are only written when you explicitly apply the change, and
the originals are snapshotted so you can revert.

## Requirements

- Node.js 20+ and pnpm
- Python 3.12+ (managed with [uv](https://docs.astral.sh/uv/))
- An OpenAI-compatible LLM endpoint for the refactoring features (optional — analysis and
  visualization work without one)

## Documentation

| | |
|---|---|
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | Why this exists and how the pieces fit |
| [docs/DESIGN.md](docs/DESIGN.md) | Schema, API, visual mapping rules (Korean) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased plan with acceptance criteria (Korean) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and conventions |

한국어 안내는 [README.ko.md](README.ko.md) 를 참고하세요.

## License

MIT — see [LICENSE](LICENSE).
