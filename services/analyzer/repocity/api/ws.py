"""One socket per project, carrying every server-side event.

Analysis progress, agent tokens and city deltas all travel here rather than on separate
per-task sockets; the client keeps one connection and routes on `type`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class Hub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def join(self, project_id: str, socket: WebSocket) -> None:
        await socket.accept()
        self._clients[project_id].add(socket)

    def leave(self, project_id: str, socket: WebSocket) -> None:
        self._clients[project_id].discard(socket)
        if not self._clients[project_id]:
            del self._clients[project_id]

    async def broadcast(self, project_id: str, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for socket in list(self._clients.get(project_id, ())):
            try:
                await socket.send_json(event)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(socket)
        for socket in dead:
            self.leave(project_id, socket)

    def emitter(self, project_id: str):
        async def emit(event: dict[str, Any]) -> None:
            await self.broadcast(project_id, event)

        return emit


hub = Hub()


@router.websocket("/ws/stream")
async def stream(socket: WebSocket, projectId: str) -> None:  # noqa: N803 - query param name
    await hub.join(projectId, socket)
    try:
        while True:
            # The client never sends anything; this keeps the connection open and notices
            # when it goes away.
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(KeyError):
            hub.leave(projectId, socket)


async def keepalive(seconds: float = 30.0) -> None:
    while True:
        await asyncio.sleep(seconds)
