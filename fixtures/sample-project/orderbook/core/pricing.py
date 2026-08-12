from decimal import Decimal

from .inventory import reserved_quantity
from .models import Order


def apply_discount(order: Order, rate: Decimal) -> Decimal:
    if rate < 0 or rate > 1:
        raise ValueError("rate must be between 0 and 1")
    return order.total * (Decimal(1) - rate)


def scarcity_multiplier(sku: str) -> Decimal:
    reserved = reserved_quantity(sku)
    if reserved > 100:
        return Decimal("1.25")
    if reserved > 50:
        return Decimal("1.10")
    return Decimal(1)
