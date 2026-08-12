from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")


def to_cents(value: Decimal) -> int:
    return int(value.quantize(CENTS, rounding=ROUND_HALF_UP) * 100)


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENTS)
