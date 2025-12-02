import os
import sys
import json
from functools import wraps
from typing import Any, Callable, TypeVar
from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])

# Tracks whether logging has been configured yet
_LOGGER_INITIALIZED = False
_COLD_START = True


# -----------------------------------------------------------------------------
# Formatters
# -----------------------------------------------------------------------------
def _lambda_json_formatter(record: dict) -> str:
    """
    JSON formatter for AWS Lambda logs. Ensures consistent structured logging.
    """
    output = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Attach Lambda-specific context if present
    context = record["extra"].get("lambda_context")
    if context:
        output.update(context)

    return json.dumps(output)


# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------
def setup_logging() -> None:
    """
    Initialize Loguru logging exactly once.

    - Local: pretty, colorized output
    - Lambda: structured JSON logs without multiprocessing
    """
    global _LOGGER_INITIALIZED

    if _LOGGER_INITIALIZED:
        return

    logger.remove()

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    common = dict(
        level=level,
        enqueue=False,        # CRITICAL: avoids multiprocessing issues on AWS Lambda
        backtrace=False,
        diagnose=False,
    )

    if is_lambda:
        # CloudWatch JSON structured logging
        logger.add(sys.stdout, serialize=False, format=_lambda_json_formatter, **common)
    else:
        # Local development: pretty logs
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> "
                   "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
                   "- <level>{message}</level>",
            colorize=True,
            **common,
        )

    _LOGGER_INITIALIZED = True
    logger.debug("Logger initialized (lambda_mode={} level={})", is_lambda, level)


# -----------------------------------------------------------------------------
# Lambda Handler Decorator
# -----------------------------------------------------------------------------
def with_logging(func: F) -> F:
    """
    Decorator for AWS Lambda handlers:
      - Ensures logging is initialized lazily
      - Injects Lambda context into logs
      - Logs entry, exit, and exceptions
      - Adds cold start metadata
    """

    @wraps(func)
    def wrapper(event: dict, context: Any, *args: Any, **kwargs: Any):

        setup_logging()

        global _COLD_START

        # Lambda context metadata
        lambda_metadata = {
            "request_id": getattr(context, "aws_request_id", None),
            "function_name": getattr(context, "function_name", None),
            "function_version": getattr(context, "function_version", None),
            "cold_start": _COLD_START,
        }

        # Bind extra metadata for all subsequent log lines
        bound_logger = logger.bind(lambda_context=lambda_metadata)

        bound_logger.info(f"Entering {func.__name__}")

        try:
            result = func(event, context, *args, **kwargs)
            bound_logger.info(f"Exiting {func.__name__}")
            return result

        except Exception:
            bound_logger.exception(f"Unhandled exception in {func.__name__}")
            raise

        finally:
            _COLD_START = False

    return wrapper  # type: ignore


# Export logger
__all__ = ["logger", "with_logging", "setup_logging"]
