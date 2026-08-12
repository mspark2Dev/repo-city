from ..core.models import Order
from ..util.money import to_cents


def order_to_dict(order: Order) -> dict:
    return {
        "orderId": order.order_id,
        "customerId": order.customer_id,
        "status": order.status,
        "totalCents": to_cents(order.total),
        "lines": [
            {"sku": line.sku, "quantity": line.quantity, "unitPrice": str(line.unit_price)}
            for line in order.lines
        ],
    }
