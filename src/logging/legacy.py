"""
Legacy logging decorator (deprecated).

Provides the @with_logging decorator for backward compatibility.
New code should use @log_lambda_handler instead.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from src.logging.config import logger

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["with_logging"]


# -----------------------------------------------------------------------------
# Legacy Decorator (deprecated, kept for backward compatibility)
# -----------------------------------------------------------------------------
def with_logging(func: F) -> F:
    """
    Decorator that logs entry, exit, and errors for any Lambda handler.

    DEPRECATED: Use @log_lambda_handler instead for better observability.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.info(f"Entering {func.__name__}")

        try:
            result = func(*args, **kwargs)
            logger.info(f"Exiting {func.__name__}")
            return result

        except Exception as e:
            logger.error(f"Unhandled exception in {func.__name__}: {e}")
            raise

    return wrapper  # type: ignore[return-value]
