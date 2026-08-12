"""Command line entry point: analyze a repository into a CityMap."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build_city
from .serialize import to_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repocity", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="analyze a repository")
    analyze.add_argument("path", type=Path)
    analyze.add_argument("-o", "--output", type=Path, help="write JSON here instead of stdout")
    analyze.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB", help="extra ignore pattern"
    )
    analyze.add_argument("--stats", action="store_true", help="print a summary to stderr")

    args = parser.parse_args(argv)

    if not args.path.is_dir():
        print(f"not a directory: {args.path}", file=sys.stderr)
        return 2

    city = build_city(args.path, tuple(args.exclude))
    payload = to_json(city)

    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    if args.stats:
        stats = json.loads(payload)["stats"]
        print(
            f"{stats['files']} files, {stats['loc']} loc, {stats['links']} links, "
            f"{stats['unresolved']} unresolved, {stats['durationMs']}ms",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
