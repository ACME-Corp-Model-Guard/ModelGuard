"""
Centralized AWS client factory with lazy initialization and caching.
Used by all Lambda functions to avoid repeating boilerplate.

Provides cached access to:
- DynamoDB resource + table accessor
- S3 client
- Cognito Identity Provider client
- Bedrock Runtime client
"""

from __future__ import annotations

from typing import Any, Optional

import boto3
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
from mypy_boto3_s3 import S3Client

from src.settings import AWS_REGION

# =====================================================================================
# Lazy-initialized client caches
# =====================================================================================

_dynamodb_resource: Optional[DynamoDBServiceResource] = None
_s3_client: Optional[S3Client] = None
_cognito_client: Optional[CognitoIdentityProviderClient] = None
_bedrock_runtime: Optional[BedrockRuntimeClient] = None


# =====================================================================================
# DynamoDB
# =====================================================================================


def get_dynamodb() -> DynamoDBServiceResource:
    """
    Return a cached DynamoDB service resource.
    """
    global _dynamodb_resource

    if boto3 is None:
        raise RuntimeError("boto3 is not available in this environment")

    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)  # type: ignore

    return _dynamodb_resource


def get_ddb_table(table_name: str) -> Any:
    """
    Convenience wrapper for DynamoDB table access.
    Returns a boto3 Table object.
    """
    dynamo: DynamoDBServiceResource = get_dynamodb()
    return dynamo.Table(table_name)  # type: ignore[no-any-return]


# =====================================================================================
# S3
# =====================================================================================


def get_s3() -> S3Client:
    """
    Return a cached S3 client.
    """
    global _s3_client

    if boto3 is None:
        raise RuntimeError("boto3 is not available in this environment")

    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)

    return _s3_client


# =====================================================================================
# Cognito
# =====================================================================================


def get_cognito() -> CognitoIdentityProviderClient:
    """
    Return a cached Cognito Identity Provider client.
    """
    global _cognito_client

    if boto3 is None:
        raise RuntimeError("boto3 is not available in this environment")

    if _cognito_client is None:
        _cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)

    return _cognito_client


# =====================================================================================
# Bedrock Runtime
# =====================================================================================


def get_bedrock_runtime(region: Optional[str] = None) -> BedrockRuntimeClient:
    """
    Return a cached AWS Bedrock Runtime client.

    Bedrock does not yet have stable boto3-stubs, so this is typed as `Any`.
    """
    global _bedrock_runtime

    if boto3 is None:
        raise RuntimeError("boto3 is not available in this environment")

    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=region or AWS_REGION,
        )

    return _bedrock_runtime
