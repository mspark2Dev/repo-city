from decimal import Decimal

from .models import Order


def settle(order: Order, region: str, currency: str, flags: dict) -> Decimal:
    """Deliberately awful: this is the high-complexity building in the city."""
    total = order.total
    if total <= 0:
        return Decimal(0)

    if region == "EU":
        if currency == "EUR":
            total *= Decimal("1.21") if flags.get("vat") else Decimal(1)
        elif currency == "GBP":
            total *= Decimal("1.20") if flags.get("vat") else Decimal(1)
        elif currency == "USD" and flags.get("convert"):
            total *= Decimal("0.92")
        else:
            total *= Decimal("1.19")
    elif region == "US":
        if flags.get("nexus") and currency == "USD":
            total *= Decimal("1.0825")
        elif flags.get("nexus"):
            total *= Decimal("1.07")
        elif currency != "USD" and flags.get("convert"):
            total *= Decimal("1.02")
    elif region == "APAC":
        if currency == "JPY":
            total *= Decimal("1.10")
        elif currency == "KRW":
            total *= Decimal("1.10") if flags.get("vat") else Decimal("1.0")
        elif currency == "SGD" or currency == "AUD":
            total *= Decimal("1.09")
        else:
            total *= Decimal("1.05")
    else:
        total *= Decimal("1.15")

    if flags.get("expedite"):
        if total > 1000:
            total += Decimal(25)
        elif total > 500:
            total += Decimal(15)
        else:
            total += Decimal(10)

    if flags.get("loyalty") and order.status == "confirmed":
        total *= Decimal("0.97")
    if flags.get("coupon") and not flags.get("loyalty"):
        total *= Decimal("0.95")
    if flags.get("round"):
        total = total.quantize(Decimal("0.01"))

    return total


def settlement_currency(region: str) -> str:
    return {"EU": "EUR", "US": "USD", "APAC": "SGD"}.get(region, "USD")
