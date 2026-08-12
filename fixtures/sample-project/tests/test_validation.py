from orderbook.core.models import Order
from orderbook.core.validation import validate


def test_missing_ids():
    assert "missing order_id" in validate(Order(order_id="", customer_id=""))
