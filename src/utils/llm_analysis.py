"""
AWS Bedrock utilities for LLM analysis.
Simple functions for any type of analysis using foundation models.
"""

import json
import os
import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from typing import Dict, Any, Optional, List, Union

from src.logger import logger


# Module-level client - reused across all function calls
_bedrock_client = None


def _get_bedrock_client() -> boto3.client:
    """Get or create singleton Bedrock runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        region = os.getenv("BEDROCK_REGION", "us-east-2")
        _bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_client


def ask_llm(
    prompt: str, max_tokens: int = 200, return_json: bool = False
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Ask the LLM a question and get a response.

    Args:
        prompt: The question or instruction to send to the model
        max_tokens: Maximum tokens in the response
        return_json: If True, parse response as JSON

    Returns:
        String response or parsed JSON dict, None if failed
    """
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")

    try:
        client = _get_bedrock_client()
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        result = json.loads(response["body"].read().decode("utf-8"))
        content = result["content"][0]["text"]

        if return_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw response: {content}")
                return None

        return content

    except (ClientError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Bedrock request failed: {e}")
        return None
