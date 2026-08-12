import re

_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")


def truncate(value: str, limit: int = 80) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
