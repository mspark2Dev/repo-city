# Contributing

epoCity is pre-alpha and the architecture is still moving. Before starting non-trivial work, open an
issue so we can agree on the approach — see [docs/DESIGN.md](docs/DESIGN.md) for the decisions
already made and their rationale.

## Development setup

> The `services/analyzer` and `apps/web` trees land with Phase 1 of the
> [roadmap](docs/ROADMAP.md); until then the steps below have nothing to run against.

```bash
git clone https://github.com/mspark2Dev/repo-city.git
cd repo-city

# Backend
cd services/analyzer
uv sync
uv run pytest

# Frontend
cd ../../apps/web
pnpm install
pnpm dev
```

Copy `.env.example` to `.env` and point `LLM_BASE_URL` at an OpenAI-compatible endpoint. The
analyzer and the 3D view work without one; only the refactoring features need it.

## Conventions

**Commits** follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add cyclomatic complexity to the metrics pipeline
fix: resolve TypeScript path aliases with a trailing wildcard
docs: document the prefix-cache prompt ordering contract
```

One commit does one thing. Do not add `Co-Authored-By` trailers.

**Python** — type hints required, `ruff` and `ruff format` clean.
**TypeScript** — `strict: true`, no `any`.

**Comments** explain *why*, not *what*. Do not restate what the code already says, and do not invent
docstrings for self-evident functions. Non-obvious algorithms (`layout.py`, `imports/`) and public
API surfaces should carry their intent and constraints.

**Schema** — `services/analyzer/epocity/schema.py` is the single source of truth for `CityMap`.
TypeScript types are generated from it (`pnpm gen:types`); never edit the generated file by hand.

## Pull requests

- Keep them focused; a PR that does two unrelated things is two PRs.
- Add tests for analyzer changes. Layout and metrics are deterministic and should be tested as such.
- Update the affected documentation in the same PR.
- Note any change to a decision recorded in `docs/DESIGN.md`, and update that document.

## Reporting bugs

Include the repository you analyzed (or a minimal reproduction), the `CityMap.json` stats block if
analysis completed, and your OS, Node, and Python versions.
