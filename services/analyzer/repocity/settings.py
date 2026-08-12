"""Runtime configuration, read from the environment (and a .env at the repository root)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")


def data_root() -> Path:
    """Where snapshots live.

    Not the cache directory: caches are disposable by definition, and these are the only
    copy of a file the agent is about to overwrite.
    """
    override = os.environ.get("REPOCITY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "repocity"


@dataclass(frozen=True, slots=True)
class LLMSettings:
    base_url: str
    model: str
    api_key: str
    max_context: int
    context_budget: int

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


@lru_cache(maxsize=1)
def llm_settings() -> LLMSettings:
    return LLMSettings(
        base_url=os.environ.get("LLM_BASE_URL", "").rstrip("/"),
        model=os.environ.get("LLM_MODEL", ""),
        api_key=os.environ.get("LLM_API_KEY", "dummy"),
        max_context=int(os.environ.get("LLM_MAX_CONTEXT", "120000")),
        context_budget=int(os.environ.get("LLM_CONTEXT_BUDGET", "60000")),
    )
