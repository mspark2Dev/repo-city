from decimal import Decimal

from orderbook.core.models import Order, OrderLine
from orderbook.core.settlement import settle


def _order(amount: str) -> Order:
    order = Order(order_id="o1", customer_id="c1")
    order.add_line(OrderLine(sku="a", quantity=1, unit_price=Decimal(amount)))
    return order


def test_empty_order_settles_to_zero():
    assert settle(Order(order_id="o", customer_id="c"), "US", "USD", {}) == Decimal(0)


def test_eu_vat():
    assert settle(_order("100"), "EU", "EUR", {"vat": True}) == Decimal("121.00")
