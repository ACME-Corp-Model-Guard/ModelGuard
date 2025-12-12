"""
Contextual logging with correlation ID and timing support.

Provides ContextualLogger that automatically injects correlation IDs and elapsed time
into all log messages for distributed request tracing.

Correlation IDs:
    A correlation ID is a unique identifier (typically a UUID) assigned to each request
    that flows through the system. It allows you to trace all log messages related to a
    single request across multiple Lambda invocations, services, and components. This is
    critical for debugging distributed systems where a single user action may trigger
    multiple asynchronous operations.

    Example: When debugging a failed artifact upload, you can filter CloudWatch logs by
    correlation_id to see the complete timeline of events for that specific request,
    even if thousands of other requests were processed simultaneously.

Elapsed Time:
    Tracks the time elapsed since the start of a request, automatically included in all
    log messages. This enables performance profiling and helps identify slow operations
    without manual timing code. You can quickly spot where time is being spent in a
    request lifecycle.

    Example: Log entries show "elapsed_ms: 1234" indicating that 1234ms have passed
    since the request started, making it easy to identify operations that exceed SLAs
    or contribute to high latency.
"""

import time
from contextvars import ContextVar
from typing import Any, Dict, Optional

from src.logging.config import logger

# Thread-safe context variables for Lambda execution tracking
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
request_start_time: ContextVar[Optional[float]] = ContextVar(
    "request_start_time", default=None
)

__all__ = ["correlation_id", "request_start_time", "ContextualLogger", "clogger"]


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

    def exception(
        self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        logger.bind(**self._add_context(extra)).exception(
            self._enrich_message(msg), **kwargs
        )


# Create singleton instance
clogger = ContextualLogger()
