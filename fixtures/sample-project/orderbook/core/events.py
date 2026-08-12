from collections.abc import Callable
from dataclasses import dataclass

Handler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers.get(event.name, []):
            handler(event)
