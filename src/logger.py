import json
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


# -----------------------------------------------------------------------------
# Context Variables for Request Tracing
# -----------------------------------------------------------------------------
# Thread-safe context variables for Lambda execution tracking
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
request_start_time: ContextVar[Optional[float]] = ContextVar(
    "request_start_time", default=None
)


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
            enqueue=False,  # sync logging
            backtrace=True,  # show full stack traces
            diagnose=False,  # SECURITY: Disabled to avoid exposing variable values
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
            enqueue=False,
            backtrace=True,
            diagnose=True,
        )

    # Log initialization message
    logger.info(f"Logging initialized with level: {log_level}")


# Initialize logging when module is imported
setup_logging()


# -----------------------------------------------------------------------------
# Sensitive Data Masking
# -----------------------------------------------------------------------------
SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "authorization",
    "x-authorization",
    "access_token",
    "id_token",
    "refresh_token",
    "api_key",
    "private_key",
    "client_secret",
    "aws_secret_access_key",
}

SENSITIVE_PATTERNS = [
    (r"bearer\s+[a-zA-Z0-9\-._~+/]+=*", "bearer [REDACTED]"),  # JWT tokens
    (r"(https?://[^\s]+presigned[^\s]*)", "[PRESIGNED_URL]"),  # S3 presigned URLs
]


def mask_sensitive_data(data: Any, max_depth: int = 5) -> Any:
    """
    Recursively mask sensitive data in dicts, lists, and strings.

    Args:
        data: Data structure to mask (dict, list, str, or primitive)
        max_depth: Maximum recursion depth to prevent infinite loops

    Returns:
        Deep copy with sensitive values masked
    """
    if max_depth <= 0:
        return "[MAX_DEPTH_EXCEEDED]"

    if isinstance(data, dict):
        return {
            k: (
                "[REDACTED]"
                if k.lower() in SENSITIVE_FIELDS
                else mask_sensitive_data(v, max_depth - 1)
            )
            for k, v in data.items()
        }

    elif isinstance(data, list):
        return [mask_sensitive_data(item, max_depth - 1) for item in data]

    elif isinstance(data, str):
        masked = data
        for pattern, replacement in SENSITIVE_PATTERNS:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
        return masked

    else:
        return data


# -----------------------------------------------------------------------------
# Contextual Logger with Correlation ID Support
# -----------------------------------------------------------------------------
class ContextualLogger:
    """
    Wrapper around loguru logger that automatically injects correlation_id and timing.
    Provides the same interface as loguru logger but with enhanced context.
    """

    def _enrich_message(self, msg: str) -> str:
        """Add correlation ID prefix if available."""
        cid = correlation_id.get()
        if cid:
            return f"[{cid[:8]}] {msg}"
        return msg

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build context dict with correlation_id and elapsed time."""
        ctx = extra.copy() if extra else {}
        cid = correlation_id.get()
        start = request_start_time.get()

        if cid:
            ctx["correlation_id"] = cid
        if start:
            ctx["elapsed_ms"] = int((time.time() - start) * 1000)

        return ctx

    def info(
        self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        logger.bind(**self._add_context(extra)).info(
            self._enrich_message(msg), **kwargs
        )

    def debug(
        self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        logger.bind(**self._add_context(extra)).debug(
            self._enrich_message(msg), **kwargs
        )

    def warning(
        self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        logger.bind(**self._add_context(extra)).warning(
            self._enrich_message(msg), **kwargs
        )

    def error(
        self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        logger.bind(**self._add_context(extra)).error(
            self._enrich_message(msg), **kwargs
        )


# Create singleton instance
clogger = ContextualLogger()


# -----------------------------------------------------------------------------
# Lambda Request/Response Logging Decorator
# -----------------------------------------------------------------------------
def log_lambda_handler(
    endpoint_name: str,
    log_request_body: bool = False,
    log_response_body: bool = False,
    mask_request: bool = True,
    mask_response: bool = True,
    validate_openapi: bool = True,
) -> Callable[[F], F]:
    """
    Comprehensive Lambda handler logging decorator.

    Features:
    - Generates correlation ID from AWS request ID
    - Logs request method, path, headers, query/path params
    - INFO level: Summary only (method, path, status, duration)
    - DEBUG level: Full request/response bodies (masked)
    - Masks sensitive data
    - Tracks execution time
    - Optional OpenAPI validation
    - Structured logging for CloudWatch Insights queries

    Args:
        endpoint_name: Human-readable endpoint name (e.g., "POST /artifact/{type}")
        log_request_body: Log request body at DEBUG level
        log_response_body: Log response body at DEBUG level
        mask_request: Whether to mask sensitive data in request
        mask_response: Whether to mask sensitive data in response
        validate_openapi: Whether to validate against OpenAPI spec

    Usage:
        @log_lambda_handler("POST /artifact/{type}")
        @auth_required
        def lambda_handler(event, context, auth):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(
            event: Dict[str, Any], context: Any, **kwargs: Any
        ) -> Dict[str, Any]:
            # Initialize correlation context
            cid = (
                context.request_id
                if hasattr(context, "request_id")
                else str(uuid.uuid4())
            )
            correlation_id.set(cid)
            request_start_time.set(time.time())

            # Extract request metadata
            http_method = event.get("httpMethod", "UNKNOWN")
            path = event.get("path", "UNKNOWN")
            headers = event.get("headers", {})
            query_params = event.get("queryStringParameters") or {}
            path_params = event.get("pathParameters") or {}

            # Log request summary (INFO level - always)
            request_log = {
                "event_type": "request",
                "endpoint": endpoint_name,
                "method": http_method,
                "path": path,
                "correlation_id": cid,
            }

            clogger.info(f"Incoming request: {http_method} {path}", extra=request_log)

            # Log detailed request at DEBUG level
            if logger._core.min_level <= 10:  # type: ignore[attr-defined]  # DEBUG = 10
                detailed_request = {
                    "event_type": "request_details",
                    "endpoint": endpoint_name,
                    "headers": (
                        mask_sensitive_data(headers) if mask_request else headers
                    ),
                    "query_params": query_params,
                    "path_params": path_params,
                }

                if log_request_body:
                    raw_body = event.get("body", "")
                    try:
                        body_dict = json.loads(raw_body) if raw_body else {}
                        detailed_request["body"] = (
                            mask_sensitive_data(body_dict)
                            if mask_request
                            else body_dict
                        )
                    except json.JSONDecodeError:
                        detailed_request["body"] = "[NON_JSON_BODY]"

                clogger.debug(
                    f"Request details: {http_method} {path}", extra=detailed_request
                )

            # Execute handler
            try:
                result = func(event, context, **kwargs)

                # Log response summary (INFO level - always)
                status_code = result.get("statusCode", 500)
                start_time = request_start_time.get()
                duration_ms = int((time.time() - (start_time or time.time())) * 1000)

                response_log = {
                    "event_type": "response",
                    "endpoint": endpoint_name,
                    "status_code": status_code,
                    "correlation_id": cid,
                    "duration_ms": duration_ms,
                }

                log_level_name = "info" if 200 <= status_code < 400 else "warning"
                log_func = getattr(clogger, log_level_name)
                log_func(
                    f"Request completed: {http_method} {path} -> {status_code} ({duration_ms}ms)",
                    extra=response_log,
                )

                # Log detailed response at DEBUG level
                if logger._core.min_level <= 10 and log_response_body:  # type: ignore[attr-defined]
                    try:
                        body_dict = json.loads(result.get("body", "{}"))
                        detailed_response = {
                            "event_type": "response_details",
                            "body": (
                                mask_sensitive_data(body_dict)
                                if mask_response
                                else body_dict
                            ),
                        }
                        clogger.debug(
                            f"Response details: {status_code}", extra=detailed_response
                        )
                    except json.JSONDecodeError:
                        pass

                # OpenAPI validation (if enabled)
                if validate_openapi:
                    try:
                        from src.utils.openapi_validation import (
                            validate_request,
                            validate_response,
                        )

                        # Validate request
                        is_valid_req, req_violations = validate_request(
                            path,
                            http_method,
                            headers,
                            query_params,
                            path_params,
                            event.get("body"),
                        )
                        if not is_valid_req:
                            clogger.warning(
                                "Request does not match OpenAPI spec",
                                extra={
                                    "event_type": "openapi_violation",
                                    "violation_type": "request",
                                    "endpoint": endpoint_name,
                                    "violations": req_violations,
                                },
                            )

                        # Validate response
                        is_valid_resp, resp_violations = validate_response(
                            path, http_method, status_code, result.get("body")
                        )
                        if not is_valid_resp:
                            clogger.warning(
                                "Response does not match OpenAPI spec",
                                extra={
                                    "event_type": "openapi_violation",
                                    "violation_type": "response",
                                    "endpoint": endpoint_name,
                                    "violations": resp_violations,
                                },
                            )
                    except ImportError:
                        # OpenAPI validation not available
                        pass
                    except Exception as e:
                        clogger.debug(
                            f"OpenAPI validation failed: {e}",
                            extra={"validation_error": str(e)},
                        )

                return result

            except Exception as e:
                start_time = request_start_time.get()
                duration_ms = int((time.time() - (start_time or time.time())) * 1000)
                clogger.error(
                    f"Request failed: {http_method} {path}",
                    extra={
                        "event_type": "error",
                        "endpoint": endpoint_name,
                        "correlation_id": cid,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "duration_ms": duration_ms,
                    },
                    exc_info=True,
                )
                raise

            finally:
                # Clean up context
                correlation_id.set(None)
                request_start_time.set(None)

        return wrapper  # type: ignore[return-value]

    return decorator


# -----------------------------------------------------------------------------
# Operation Timing Context Manager
# -----------------------------------------------------------------------------
@contextmanager
def log_operation(
    operation_name: str, log_level: str = "debug", **metadata: Any
) -> Any:
    """
    Context manager for timing and logging operations.

    Usage:
        with log_operation('fetch_metadata', artifact_id='123'):
            metadata = fetch_artifact_metadata(url)
        # Automatically logs: "Operation 'fetch_metadata' completed in 234ms"

    Args:
        operation_name: Name of the operation being performed
        log_level: Log level for completion message (default: debug)
        **metadata: Additional context to include in logs
    """
    start = time.time()
    clogger.debug(f"Starting operation: {operation_name}", extra=metadata)

    try:
        yield
        duration_ms = int((time.time() - start) * 1000)
        log_func = getattr(clogger, log_level)
        log_func(
            f"Operation completed: {operation_name} ({duration_ms}ms)",
            extra={**metadata, "duration_ms": duration_ms, "status": "success"},
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        clogger.error(
            f"Operation failed: {operation_name} ({duration_ms}ms)",
            extra={
                **metadata,
                "duration_ms": duration_ms,
                "status": "failure",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        raise


# -----------------------------------------------------------------------------
# Batch Operation Logger
# -----------------------------------------------------------------------------
class BatchOperationLogger:
    """
    Logger for batch operations (e.g., computing multiple metrics).
    Automatically tracks progress and provides summary.

    Usage:
        with BatchOperationLogger('compute_metrics', total=10) as batch:
            for metric in metrics:
                batch.log_item(metric.name, status='success', score=0.85)
    """

    def __init__(self, operation_name: str, total: Optional[int] = None):
        self.operation_name = operation_name
        self.total = total
        self.results: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None

    def __enter__(self) -> "BatchOperationLogger":
        self.start_time = time.time()
        clogger.info(
            f"Starting batch operation: {self.operation_name}",
            extra={"total_items": self.total},
        )
        return self

    def log_item(
        self, item_name: str, status: str = "success", **metadata: Any
    ) -> None:
        """Log progress for individual item."""
        self.results.append({"item": item_name, "status": status, **metadata})

        progress_msg = (
            f"[{len(self.results)}/{self.total}]"
            if self.total
            else f"[{len(self.results)}]"
        )
        clogger.debug(
            f"{progress_msg} {item_name}: {status}",
            extra={"item": item_name, "status": status, **metadata},
        )

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        duration_ms = int((time.time() - self.start_time) * 1000)  # type: ignore

        success_count = sum(1 for r in self.results if r["status"] == "success")
        failure_count = len(self.results) - success_count

        summary = {
            "operation": self.operation_name,
            "duration_ms": duration_ms,
            "total_items": len(self.results),
            "success_count": success_count,
            "failure_count": failure_count,
        }

        if exc_type is None:
            clogger.info(
                f"Batch operation completed: {self.operation_name} "
                f"({success_count}/{len(self.results)} succeeded in {duration_ms}ms)",
                extra=summary,
            )
        else:
            clogger.error(
                f"Batch operation failed: {self.operation_name}",
                extra={**summary, "error_type": exc_type.__name__},
                exc_info=True,
            )


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


# Export for convenience
__all__ = [
    "logger",
    "clogger",
    "log_lambda_handler",
    "log_operation",
    "BatchOperationLogger",
    "mask_sensitive_data",
    "with_logging",
]
