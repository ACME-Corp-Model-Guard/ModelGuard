"""
Global application settings loaded from environment variables.
Used throughout the Lambda functions and shared utility modules.
"""

from __future__ import annotations

import os


# -----------------------------------------------------------------------------
# Helper: Fetch Required Environment Variables
# -----------------------------------------------------------------------------
def _require_env(name: str) -> str:
    """
    Fetch a REQUIRED environment variable or raise a descriptive error.
    """
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# -----------------------------------------------------------------------------
# Core AWS & Application Settings
# -----------------------------------------------------------------------------
AWS_REGION: str = _require_env("AWS_REGION")

# DynamoDB tables
ARTIFACTS_TABLE: str = _require_env("ARTIFACTS_TABLE")
REJECTED_ARTIFACTS_TABLE: str = _require_env("REJECTED_ARTIFACTS_TABLE")
TOKENS_TABLE: str = _require_env("TOKENS_TABLE")
FINGERPRINTS_TABLE: str = _require_env("FINGERPRINTS_TABLE")

# S3 bucket
ARTIFACTS_BUCKET: str = _require_env("ARTIFACTS_BUCKET")
JS_PROGRAMS_BUCKET: str = _require_env("JS_PROGRAMS_BUCKET")
JS_PROGRAMS_PREFIX: str = os.environ.get("JS_PROGRAMS_PREFIX", "admin-scripts/")

# Cognito
USER_POOL_ID: str = _require_env("USER_POOL_ID")
USER_POOL_CLIENT_ID: str = _require_env("USER_POOL_CLIENT_ID")

# Lambda function names
JS_RUNNER_LAMBDA_NAME: str = _require_env("JS_RUNNER_LAMBDA_NAME")

# Logging Configuration (Optional)
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


# -----------------------------------------------------------------------------
# Bedrock Settings
# -----------------------------------------------------------------------------
# BEDROCK_MODEL_ID is optional but we provide a safe default to avoid breakage.
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.amazon.nova-lite-v1:0",
)

# BEDROCK_REGION defaults to AWS_REGION if not explicitly defined.
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", "us-east-1")


# -----------------------------------------------------------------------------
# Default Admin User Settings for /reset Endpoint
# -----------------------------------------------------------------------------
ADMIN_SECRET_NAME: str = "DEFAULT_ADMIN_INFO"
DEFAULT_ADMIN_GROUP: str = "Admin"


# -----------------------------------------------------------------------------
# Quality Threshold Settings
# -----------------------------------------------------------------------------
# Minimum score threshold for each non-latency metric (0.0 to 1.0)
# Model artifacts must score at least this value on ALL metrics to be ingestible
MINIMUM_METRIC_THRESHOLD: float = float(os.environ.get("MINIMUM_METRIC_THRESHOLD", "0.5"))
