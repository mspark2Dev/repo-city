from decimal import Decimal

from ..adapters.repository import InMemoryOrderRepository
from ..core.settlement import settle, settlement_currency
from ..core.validation import validate
from .serializers import order_to_dict

_REPO = InMemoryOrderRepository()


def get_order(order_id: str) -> dict | None:
    order = _REPO.get(order_id)
    return order_to_dict(order) if order else None


def post_settlement(order_id: str, region: str) -> dict:
    order = _REPO.get(order_id)
    if order is None:
        return {"error": "not found"}
    errors = validate(order)
    if errors:
        return {"errors": errors}
    currency = settlement_currency(region)
    amount = settle(order, region, currency, {"vat": True, "round": True})
    return {"orderId": order_id, "amount": str(amount), "currency": currency}


def health() -> dict:
    return {"status": "ok", "version": "0.3.1", "minimum": str(Decimal(0))}
