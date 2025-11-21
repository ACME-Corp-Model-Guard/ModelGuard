"""
Shared decorators for logging, exception translation, and authorization
in Lambda handlers.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, TypeVar

from src.logger import logger
from src.utils.http import LambdaResponse, error_response

F = TypeVar("F", bound=Callable[..., Any])


# -----------------------------------------------------------------------------
# Logging decorator
# -----------------------------------------------------------------------------
def with_logging(func: F) -> F:
    """
    Decorator that logs entry, exit, and errors for any Lambda handler.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.info(f"Entering {func.__name__}")

        try:
            result = func(*args, **kwargs)
            logger.info(f"Exiting {func.__name__}")
            return result

        except Exception as e:
            logger.error(
                f"Unhandled exception in {func.__name__}: {e}",
                exc_info=True,
            )
            raise

    return wrapper  # type: ignore[return-value]


# -----------------------------------------------------------------------------
# Exception → API Gateway response translator
# -----------------------------------------------------------------------------
def translate_exceptions(func: F) -> Callable[[Dict[str, Any], Any], LambdaResponse]:
    """
    Decorator for Lambda handlers that ensures all uncaught exceptions
    become standardized JSON error responses.
    """

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Any) -> LambdaResponse:
        try:
            return func(event, context)

        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            return error_response(
                500,
                f"Internal Server Error: {e}",
                error_code="INTERNAL_ERROR",
            )

    return wrapper
