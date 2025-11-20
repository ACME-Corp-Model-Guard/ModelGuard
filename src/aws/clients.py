"""
Centralized AWS client factory with lazy initialization and caching.
Used by all Lambda functions to avoid repeating boilerplate.
"""

from __future__ import annotations

from typing import Optional, Any

import boto3
from botocore.client import BaseClient
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

from src.settings import AWS_REGION


# -------------------------------------------------------------------------------------
# Lazy-initialized client caches
# -------------------------------------------------------------------------------------
_dynamodb_resource: Optional[DynamoDBServiceResource] = None
_s3_client: Optional[BaseClient] = None
_cognito_client: Optional[BaseClient] = None


# -------------------------------------------------------------------------------------
# DynamoDB
# -------------------------------------------------------------------------------------
def get_dynamodb() -> DynamoDBServiceResource:
    """
    Returns a cached DynamoDB resource.
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


# -------------------------------------------------------------------------------------
# S3
# -------------------------------------------------------------------------------------
def get_s3() -> BaseClient:
    """
    Returns a cached S3 client.
    """
    global _s3_client

    if boto3 is None:
        raise RuntimeError("boto3 is not available in this environment")

    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)

    return _s3_client


# -------------------------------------------------------------------------------------
# Cognito
# -------------------------------------------------------------------------------------
def get_cognito() -> BaseClient:
    """
    Returns a cached Cognito Identity Provider client.
    """
    global _cognito_cli
