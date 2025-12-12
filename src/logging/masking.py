"""
Sensitive data masking utilities for secure logging.

Provides utilities to recursively mask sensitive data (tokens, passwords, secrets)
in data structures before logging to prevent credential exposure.
"""

import re
from typing import Any, List, Set, Tuple

# Sensitive field names that should always be masked
SENSITIVE_FIELDS: Set[str] = {
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

# Regex patterns for masking sensitive data in strings
SENSITIVE_PATTERNS: List[Tuple[str, str]] = [
    (r"bearer\s+[a-zA-Z0-9\-._~+/]+=*", "bearer [REDACTED]"),  # JWT tokens
    (r"(https?://[^\s]+presigned[^\s]*)", "[PRESIGNED_URL]"),  # S3 presigned URLs
]

__all__ = ["mask_sensitive_data", "SENSITIVE_FIELDS", "SENSITIVE_PATTERNS"]


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
