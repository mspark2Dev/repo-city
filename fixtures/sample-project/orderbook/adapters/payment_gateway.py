from decimal import Decimal

from ..util.retry import with_retry


class PaymentGateway:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def charge(self, customer_id: str, amount: Decimal) -> str:
        return with_retry(lambda: self._post(customer_id, amount))

    def _post(self, customer_id: str, amount: Decimal) -> str:
        if amount <= 0:
            raise ValueError("amount must be positive")
        return f"txn-{customer_id}-{amount}"
