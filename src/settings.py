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
TOKENS_TABLE: str = _require_env("TOKENS_TABLE")

# S3 bucket
ARTIFACTS_BUCKET: str = _require_env("ARTIFACTS_BUCKET")

# Cognito
USER_POOL_ID: str = _require_env("USER_POOL_ID")
USER_POOL_CLIENT_ID: str = _require_env("USER_POOL_CLIENT_ID")

# Logging Configuration (Optional)
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


# -----------------------------------------------------------------------------
# Bedrock Settings
# -----------------------------------------------------------------------------
# BEDROCK_MODEL_ID is optional but we provide a safe default to avoid breakage.
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
)

# BEDROCK_REGION defaults to AWS_REGION if not explicitly defined.
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", AWS_REGION)


# -----------------------------------------------------------------------------
# Default Admin User Settings for /reset Endpoint
# -----------------------------------------------------------------------------
DEFAULT_ADMIN_USERNAME: str = "ece30861defaultadminuser"
DEFAULT_ADMIN_PASSWORD: str = (
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
)
DEFAULT_ADMIN_GROUP: str = "Admin"
