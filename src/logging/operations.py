"""
Operation timing and batch operation tracking.

Provides utilities for timing operations and tracking progress of batch operations
like metric computation or file processing.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from src.logging.context import clogger

__all__ = ["log_operation", "BatchOperationLogger"]


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
        clogger.exception(
            f"Operation failed: {operation_name} ({duration_ms}ms)",
            extra={
                **metadata,
                "duration_ms": duration_ms,
                "status": "failure",
                "error_type": type(e).__name__,
            },
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
            clogger.exception(
                f"Batch operation failed: {self.operation_name}",
                extra={**summary, "error_type": exc_type.__name__},
            )
