"""Adapter over an OpenAI-compatible chat endpoint.

Nothing above this module knows which runtime is serving the model, so vLLM, Ollama and
LM Studio are interchangeable and a failing remote server can fall back to a local one.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from ..settings import LLMSettings, llm_settings

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 300.0


class LLMUnavailable(RuntimeError):
    """The endpoint could not be reached or refused the request."""


@dataclass(frozen=True, slots=True)
class Health:
    ok: bool
    model: str | None = None
    detail: str | None = None


class LLMAdapter:
    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or llm_settings()

    @property
    def configured(self) -> bool:
        return self.settings.configured

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> Health:
        if not self.configured:
            return Health(ok=False, detail="LLM_BASE_URL or LLM_MODEL is not set")
        try:
            async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT) as client:
                response = await client.get(
                    f"{self.settings.base_url}/models", headers=self._headers()
                )
                response.raise_for_status()
                served = [m["id"] for m in response.json().get("data", [])]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            return Health(ok=False, detail=str(exc))

        if self.settings.model not in served:
            return Health(ok=False, detail=f"{self.settings.model} not served; has {served}")
        return Health(ok=True, model=self.settings.model)

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict | None = None, max_tokens: int = 2048
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            # Guided decoding: the server guarantees the shape, so there is no parse
            # failure path to handle and no need to ask the model for JSON in prose.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": schema},
            }

        timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.settings.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMUnavailable(str(exc)) from exc

    async def stream(
        self, messages: list[dict[str, str]], *, max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }
        timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as client,
                client.stream(
                    "POST",
                    f"{self.settings.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        return
                    delta = _content_of(chunk)
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            raise LLMUnavailable(str(exc)) from exc

    async def prewarm(self, messages: list[dict[str, str]]) -> None:
        """Fire the cacheable prefix so the user's first real command hits a warm cache."""
        with contextlib.suppress(LLMUnavailable):
            await self.complete(messages, max_tokens=1)


def _content_of(chunk: str) -> str:
    try:
        return json.loads(chunk)["choices"][0]["delta"].get("content") or ""
    except (ValueError, KeyError, IndexError):
        return ""
