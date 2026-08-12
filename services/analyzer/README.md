# repocity-analyzer

Static analysis backend for repoCity. Parses a repository with tree-sitter and emits a `CityMap`.

```bash
uv sync
uv run repocity analyze ../../fixtures/sample-project -o citymap.json
uv run uvicorn repocity.app:app --port 8787
```
