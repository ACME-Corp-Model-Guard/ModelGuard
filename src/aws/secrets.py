"""
Centralized AWS Secrets Manager client factory with lazy initialization and caching.
"""

import json
from src.aws.clients import get_secrets_manager
from src.logging.clogger import clogger


def get_secret(secret_name: str) -> dict:
    """
    retrieve secret dict from AWS Secrets Manager

    Args:
        secret_name: name of the secret to retrieve

    Returns:
        dict: secret value as a dictionary
    """
    client = get_secrets_manager()
    response = client.get_secret_value(SecretId=secret_name)
    secret = response["SecretString"]
    return json.loads(secret)


def get_secret_value(secret_name: str, value: str) -> str:
    """
    retrieve secret value from AWS Secrets Manager

    Args:
        secret_name: name of the secret to retrieve
        value: key of the secret value to retrieve
    Returns:
        str: secret value as a string
    """
    clogger.debug(f"Retrieving secret '{secret_name}' value for key '{value}'")
    secret_dict = get_secret(secret_name)
    return secret_dict[value]
