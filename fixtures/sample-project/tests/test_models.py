from decimal import Decimal

from orderbook.core.models import Order, OrderLine


def test_subtotal():
    line = OrderLine(sku="a", quantity=3, unit_price=Decimal(2))
    assert line.subtotal == Decimal(6)


def test_order_total():
    order = Order(order_id="o1", customer_id="c1")
    order.add_line(OrderLine(sku="a", quantity=2, unit_price=Decimal("1.50")))
    assert order.total == Decimal("3.00")
