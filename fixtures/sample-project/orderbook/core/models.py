from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    order_id: str
    customer_id: str
    lines: list[OrderLine] = field(default_factory=list)
    placed_at: datetime | None = None
    status: str = "draft"

    @property
    def total(self) -> Decimal:
        return sum((line.subtotal for line in self.lines), Decimal(0))

    def add_line(self, line: OrderLine) -> None:
        self.lines.append(line)
