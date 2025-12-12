"""
ModelGuard logging infrastructure.

Provides comprehensive logging utilities for AWS Lambda handlers including:
- Structured logging with loguru
- Correlation ID tracking
- Sensitive data masking
- Request/response logging with OpenAPI validation
- Operation timing and batch processing tracking

Usage:
    from src.logging import clogger, log_lambda_handler

    @log_lambda_handler("POST /artifact/{type}")
    def lambda_handler(event, context):
        clogger.info("Processing request", extra={"artifact_type": "model"})
        ...
"""

# Import and re-export all public components
from src.logging.config import logger, setup_logging
from src.logging.context import clogger, correlation_id, request_start_time
from src.logging.decorators import log_lambda_handler
from src.logging.legacy import with_logging
from src.logging.masking import mask_sensitive_data
from src.logging.operations import BatchOperationLogger, log_operation

# Initialize logging when package is imported (same as original behavior)
setup_logging()

# Define public API
__all__ = [
    # Core logger instances
    "logger",  # Raw loguru logger
    "clogger",  # Contextual logger with correlation ID
    # Decorators
    "log_lambda_handler",  # Lambda handler logging (primary)
    "with_logging",  # Legacy decorator (deprecated)
    # Context managers and utilities
    "log_operation",  # Operation timing
    "BatchOperationLogger",  # Batch operation tracking
    "mask_sensitive_data",  # Data masking utility
    # Context variables (for advanced usage)
    "correlation_id",
    "request_start_time",
    # Configuration
    "setup_logging",
]
