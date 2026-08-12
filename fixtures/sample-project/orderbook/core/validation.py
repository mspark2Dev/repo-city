from .models import Order

MAX_LINES = 200


def validate(order: Order) -> list[str]:
    errors: list[str] = []
    if not order.order_id:
        errors.append("missing order_id")
    if not order.customer_id:
        errors.append("missing customer_id")
    if len(order.lines) > MAX_LINES:
        errors.append("too many lines")
    for line in order.lines:
        if line.quantity <= 0:
            errors.append(f"invalid quantity for {line.sku}")
        if line.unit_price < 0:
            errors.append(f"negative price for {line.sku}")
    return errors
