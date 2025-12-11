"""
Compatibility shim for src.logger module.

This module has been refactored into the src.logging package for better organization.
All imports are re-exported from src.logging for backward compatibility.

Existing code using `from src.logger import ...` will continue to work without changes.

New code should prefer importing from src.logging:
    from src.logging import clogger, log_lambda_handler
"""

# Re-export everything from src.logging
from src.logging import *  # noqa: F401, F403

# Explicit __all__ for clarity (same as src.logging)
__all__ = [  # noqa: F405
    "logger",
    "clogger",
    "log_lambda_handler",
    "log_operation",
    "BatchOperationLogger",
    "mask_sensitive_data",
    "with_logging",
    "correlation_id",
    "request_start_time",
    "setup_logging",
]
