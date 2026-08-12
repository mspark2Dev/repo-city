"""Writes the CityMap JSON Schema for the TypeScript type generator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repocity.schema import CityMap  # noqa: E402


def _drop_property_titles(node: object) -> None:
    """Pydantic titles every field; json-schema-to-typescript turns each into a named
    alias (Loc1, X2, ...). Removing them keeps the generated types readable."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop in value.values():
                    if isinstance(prop, dict):
                        prop.pop("title", None)
            _drop_property_titles(value)
    elif isinstance(node, list):
        for item in node:
            _drop_property_titles(item)


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("citymap.schema.json")
    schema = CityMap.model_json_schema(by_alias=True)
    _drop_property_titles(schema)
    schema["title"] = "CityMap"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
