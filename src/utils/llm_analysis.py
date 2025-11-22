"""
LLM analysis utilities using AWS Bedrock Runtime.

Provides a simple, unified interface for submitting prompts to a
foundation model through Amazon Bedrock, returning either raw text or
JSON-parsed content depending on the caller's needs.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from botocore.exceptions import ClientError
from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

from src.aws.clients import get_bedrock_runtime
from src.logger import logger
from src.settings import BEDROCK_MODEL_ID, BEDROCK_REGION


# ====================================================================================
# High-Level LLM Request
# ====================================================================================

def ask_llm(
    prompt: str,
    max_tokens: int = 200,
    return_json: bool = False,
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Submit a prompt to the configured Bedrock foundation model.

    Args:
        prompt:
            User-supplied text prompt.
        max_tokens:
            Maximum tokens allowed in the model response.
        return_json:
            If True, attempt to parse the model's output as JSON.

    Returns:
        - str: raw text returned by the LLM
        - dict: parsed JSON if return_json=True and valid JSON is produced
        - None: on failure or malformed model output
    """

    model_id = BEDROCK_MODEL_ID

    try:
        client: BedrockRuntimeClient = get_bedrock_runtime(region=BEDROCK_REGION)

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        logger.debug(f"[llm] Invoking Bedrock model '{model_id}'")

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
        )

        # Bedrock returns a streaming-like object via response["body"]
        raw_bytes = response["body"].read()
        raw_text = raw_bytes.decode("utf-8")  # outer JSON wrapper

        parsed = json.loads(raw_text)
        content = parsed["content"][0]["text"]

        if return_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("[llm] Failed to decode JSON from LLM response")
                logger.debug(f"[llm] Raw model output for debugging: {content}")
                return None

        return content

    except (ClientError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"[llm] Bedrock request failed: {e}", exc_info=True)
        return None
