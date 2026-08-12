import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retry(fn: Callable[[], T], attempts: int = 3, delay: float = 0.1) -> T:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(delay * (2**attempt))
    raise last if last else RuntimeError("retry failed")
