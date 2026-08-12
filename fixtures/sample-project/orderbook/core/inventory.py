from decimal import Decimal

from .models import Order

_RESERVATIONS: dict[str, int] = {}


def reserve(order: Order) -> None:
    for line in order.lines:
        _RESERVATIONS[line.sku] = _RESERVATIONS.get(line.sku, 0) + line.quantity


def reserved_quantity(sku: str) -> int:
    return _RESERVATIONS.get(sku, 0)


def release(sku: str, quantity: int) -> None:
    remaining = max(0, _RESERVATIONS.get(sku, 0) - quantity)
    _RESERVATIONS[sku] = remaining


def restock_value(sku: str, unit_price: Decimal) -> Decimal:
    # Imports pricing lazily; the module-level cycle with pricing.py is intentional.
    from .pricing import scarcity_multiplier

    return unit_price * reserved_quantity(sku) * scarcity_multiplier(sku)
