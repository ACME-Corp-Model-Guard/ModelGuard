import os
import sys
from functools import wraps
from typing import Any, Callable, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------
def setup_logging() -> None:
    """
    Configure Loguru logging for both local development and AWS Lambda.

    Local: Pretty console output
    Lambda: JSON structured logging to CloudWatch
    """
    # Remove default logger
    logger.remove()

    # Get log level from environment (default: INFO)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Handle silent logging
    if log_level in {"0", "OFF", "NONE", "SILENT"}:
        return  # No logging

    # Handle numeric levels
    if log_level == "1":
        log_level = "INFO"
    elif log_level == "2":
        log_level = "DEBUG"

    # Check if running in AWS Lambda
    is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    if is_lambda:
        # AWS Lambda: JSON format for CloudWatch
        logger.add(
            sys.stdout,
            level=log_level,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}"
            ),
            serialize=True,  # JSON output for CloudWatch
            enqueue=True,  # async logging
            backtrace=True,  # show full stack traces
            diagnose=True,  # show variable values in stack traces (may expose sensitive info)
        )
    else:
        # Local development: Pretty format
        logger.add(
            sys.stdout,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

    # Log initialization message
    logger.info(f"Logging initialized with level: {log_level}")


# Initialize logging when module is imported
setup_logging()

# Export the main logger for convenience
__all__ = ["logger"]


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
