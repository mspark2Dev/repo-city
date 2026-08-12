from ..core.events import Event, EventBus
from ..util.text import truncate


class LogNotifier:
    def __init__(self, bus: EventBus) -> None:
        bus.subscribe("order.settled", self.on_settled)

    def on_settled(self, event: Event) -> None:
        print(truncate(f"settled: {event.payload}"))
