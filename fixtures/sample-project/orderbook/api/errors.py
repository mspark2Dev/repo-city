class OrderbookError(Exception):
    pass


class NotFound(OrderbookError):
    pass


class ValidationFailed(OrderbookError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
