"""
Lambda handler logging decorator with OpenAPI validation.

Provides comprehensive request/response logging for AWS Lambda handlers with:
- Correlation ID tracking
- Timing and performance metrics
- Sensitive data masking
- OpenAPI specification validation
"""

import json
import time
import uuid
from functools import wraps
from typing import Any, Callable, Dict, TypeVar

from src.logutil.config import logger
from src.logutil.context import clogger, correlation_id, request_start_time
from src.logutil.masking import mask_sensitive_data

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["log_lambda_handler"]


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
                clogger.exception(
                    f"Request failed: {http_method} {path}",
                    extra={
                        "event_type": "error",
                        "endpoint": endpoint_name,
                        "correlation_id": cid,
                        "duration_ms": duration_ms,
                        "error_type": type(e).__name__,
                    },
                )
                raise

            finally:
                # Clean up context
                correlation_id.set(None)
                request_start_time.set(None)

        return wrapper  # type: ignore[return-value]

    return decorator
