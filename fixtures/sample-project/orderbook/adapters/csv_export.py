import csv
import io

from ..core.models import Order
from ..util.money import to_cents


def export(orders: list[Order]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["order_id", "customer_id", "status", "total_cents"])
    for order in orders:
        writer.writerow([order.order_id, order.customer_id, order.status, to_cents(order.total)])
    return buffer.getvalue()
