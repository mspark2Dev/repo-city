from decimal import Decimal

from .adapters.notifier import LogNotifier
from .adapters.payment_gateway import PaymentGateway
from .adapters.repository import InMemoryOrderRepository
from .core.events import Event, EventBus
from .core.inventory import reserve
from .core.models import Order
from .core.pricing import apply_discount
from .core.settlement import settle
from .core.validation import validate
from .util.clock import now


class OrderService:
    def __init__(self, gateway: PaymentGateway) -> None:
        self.repo = InMemoryOrderRepository()
        self.bus = EventBus()
        self.gateway = gateway
        self.notifier = LogNotifier(self.bus)

    def place(self, order: Order, discount: Decimal = Decimal(0)) -> dict:
        errors = validate(order)
        if errors:
            return {"errors": errors}

        order.placed_at = now()
        order.status = "confirmed"
        reserve(order)
        self.repo.save(order)

        amount = apply_discount(order, discount)
        total = settle(order, "US", "USD", {"nexus": True, "round": True})
        reference = self.gateway.charge(order.customer_id, total)
        self.bus.publish(Event("order.settled", {"orderId": order.order_id, "ref": reference}))
        return {"orderId": order.order_id, "discounted": str(amount), "settled": str(total)}
