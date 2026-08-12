"""Task orchestration: plan, generate, verify, diff.

Nothing here writes to disk. A task ends holding a proposal; applying it is a separate,
explicit action the user takes after reading the diff.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..schema import Building, CityMap
from .context import PLAN_INSTRUCTION, PLAN_SCHEMA, build_context
from .llm import LLMAdapter, LLMUnavailable
from .patch import unified_diff
from .verify import Verdict, strip_fence, verify

Emit = Callable[[dict[str, Any]], Awaitable[None]]
Status = Literal["queued", "planning", "generating", "verifying", "ready", "error"]

SYNTAX_RETRIES = 1
"""One retry on unparsable output; beyond that the model is not going to get there."""


@dataclass(slots=True)
class Task:
    id: str
    project_id: str
    node_id: str
    instruction: str
    status: Status = "queued"
    steps: list[str] = field(default_factory=list)
    diff: str | None = None
    proposal: str | None = None
    verdict: Verdict | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "taskId": self.id,
            "status": self.status,
            "nodeId": self.node_id,
            "steps": self.steps,
            "diff": self.diff,
            "verdict": self.verdict.as_dict() if self.verdict else None,
            "error": self.error,
        }


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._running: dict[str, asyncio.Task[None]] = {}

    def create(self, project_id: str, node_id: str, instruction: str) -> Task:
        task = Task(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            node_id=node_id,
            instruction=instruction,
        )
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def spawn(self, task: Task, coro: Coroutine[Any, Any, None]) -> None:
        """Run a task in the background, holding a reference to it.

        asyncio only keeps a weak reference to running tasks, so a fire-and-forget
        create_task can be garbage-collected mid-flight and reported as cancelled.
        """
        running = asyncio.ensure_future(coro)
        self._running[task.id] = running
        running.add_done_callback(lambda _: self._running.pop(task.id, None))


async def run_refactor(
    task: Task, city: CityMap, building: Building, adapter: LLMAdapter, emit: Emit
) -> None:
    try:
        context = build_context(city, building, task.instruction)
    except FileNotFoundError:
        await _fail(task, emit, "source file is gone; re-analyze the project", "context")
        return

    try:
        task.status = "planning"
        plan_messages = [
            *context.prefix,
            {"role": "user", "content": f"{PLAN_INSTRUCTION}\n\nINSTRUCTION: {task.instruction}"},
        ]
        raw_plan = await adapter.complete(plan_messages, schema=PLAN_SCHEMA, max_tokens=500)
        task.steps = json.loads(raw_plan).get("steps", [])
        await emit({"type": "agent.plan", "taskId": task.id, "steps": task.steps})

        task.status = "generating"
        proposal = await _generate(task, context.messages, adapter, emit)

        task.status = "verifying"
        for attempt in range(SYNTAX_RETRIES + 1):
            verdict = verify(
                context.source, proposal, building.lang, Path(city.root) / building.path
            )
            if verdict.parses:
                task.verdict = verdict
                break
            if attempt == SYNTAX_RETRIES:
                await _fail(
                    task, emit, "the model produced code that does not parse", "verification"
                )
                return
            await emit({"type": "agent.retry", "taskId": task.id, "reason": "output did not parse"})
            retry = [
                *context.messages,
                {"role": "assistant", "content": proposal},
                {
                    "role": "user",
                    "content": (
                        "That output is not valid syntax. Return the corrected complete file."
                    ),
                },
            ]
            proposal = await _generate(task, retry, adapter, emit)

        task.proposal = proposal
        task.diff = unified_diff(context.source, proposal, building.path)
        task.status = "ready"
        await emit(
            {
                "type": "agent.diff",
                "taskId": task.id,
                "diff": task.diff,
                "path": building.path,
                # The finished file, not the raw stream: the client would otherwise have to
                # re-implement fence stripping and would render half-written code as a diff.
                "proposal": task.proposal,
                "verdict": task.verdict.as_dict() if task.verdict else None,
            }
        )

    except LLMUnavailable as exc:
        await _fail(task, emit, f"model endpoint unavailable: {exc}", "llm")
    except (ValueError, KeyError) as exc:
        await _fail(task, emit, f"unexpected response from the model: {exc}", "protocol")
    except asyncio.CancelledError:
        task.status = "error"
        task.error = "cancelled"
        raise


async def _generate(
    task: Task, messages: list[dict[str, str]], adapter: LLMAdapter, emit: Emit
) -> str:
    chunks: list[str] = []
    async for delta in adapter.stream(messages, max_tokens=6000):
        chunks.append(delta)
        await emit({"type": "agent.token", "taskId": task.id, "delta": delta})
    return strip_fence("".join(chunks))


async def _fail(task: Task, emit: Emit, message: str, stage: str) -> None:
    task.status = "error"
    task.error = message
    await emit({"type": "agent.error", "taskId": task.id, "message": message, "stage": stage})
