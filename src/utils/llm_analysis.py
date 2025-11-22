"""
LLM analysis utilities using AWS Bedrock Runtime.

Provides:
- ask_llm(): unified function for Bedrock inference
- build_llm_prompt(): generic structured prompt builder
- build_file_analysis_prompt(): helper for metrics analyzing code/dataset files
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from botocore.exceptions import ClientError
from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

from src.aws.clients import get_bedrock_runtime
from src.logger import logger
from src.settings import BEDROCK_MODEL_ID, BEDROCK_REGION


# ====================================================================================
# ASK LLM (BEDROCK MODEL INVOCATION)
# ====================================================================================
# Send a prompt to a Bedrock foundation model and return the text or JSON output.
#
# This helper:
#   1. Builds a Bedrock "invoke_model" request
#   2. Reads the streaming-like response body
#   3. Extracts the model-generated text
#   4. Optionally parses returned content as JSON
#
# If the request fails:
#   - Logs the failure
#   - Returns None
#
# Usage:
#     response = ask_llm("Explain this code")
#     data = ask_llm(prompt, return_json=True)
# ------------------------------------------------------------------------------------


def ask_llm(
    prompt: str,
    max_tokens: int = 200,
    return_json: bool = False,
) -> Optional[Union[str, Dict[str, Any]]]:
    """Invoke a Bedrock LLM and return text or parsed JSON."""

    model_id = BEDROCK_MODEL_ID

    try:
        client: BedrockRuntimeClient = get_bedrock_runtime(region=BEDROCK_REGION)

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        logger.debug(f"[llm] Invoking Bedrock model '{model_id}'")

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
        )

        raw_bytes = response["body"].read()
        raw_text = raw_bytes.decode("utf-8")

        parsed = json.loads(raw_text)
        content = parsed["content"][0]["text"]

        if return_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("[llm] Failed to decode JSON from LLM output")
                logger.debug(f"[llm] Raw output:\n{content}")
                return None

        return content

    except (ClientError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"[llm] Bedrock request failed: {e}", exc_info=True)
        return None


# ====================================================================================
# GENERIC PROMPT BUILDER
# ====================================================================================
# Build a structured multi-section prompt suitable for LLM evaluation.
#
# This helper:
#   1. Inserts a main instruction block
#   2. Appends one or more titled sections
#   3. Produces a consistent multi-block prompt format
#
# Useful for:
#   - Code-quality analysis
#   - Dataset-quality analysis
#   - Any metric using LLM-based static review
#
# Usage:
#     prompt = build_llm_prompt(
#         instructions="Explain the following code:",
#         sections={"example.py": "def foo(): pass"},
#     )
# ------------------------------------------------------------------------------------


def build_llm_prompt(
    instructions: str,
    sections: Optional[Dict[str, str]] = None,
) -> str:
    """Construct a structured prompt with instructions and sectioned content."""

    parts: List[str] = []

    # Instructions
    parts.append(instructions.strip() + "\n\n")

    # Section blocks
    if sections:
        for title, content in sections.items():
            parts.append(f"=== {title} ===\n")
            parts.append(content)
            parts.append("\n")

    prompt = "\n".join(parts)

    logger.debug(
        f"[llm_prompt_builder] Built prompt with "
        f"{1 + (len(sections) if sections else 0)} block(s)"
    )

    return prompt


# ====================================================================================
# FILE ANALYSIS PROMPT BUILDER
# ====================================================================================
# Build a standardized prompt for metrics that analyze sets of files
# (e.g., code quality, dataset quality, reproducibility).
#
# This helper:
#   1. Defines metric-specific evaluation instructions
#   2. Enforces strict JSON output (e.g., {"code_quality": 0.73})
#   3. Adds each provided file as a separate prompt section
#
# Usage:
#     prompt = build_file_analysis_prompt(
#         metric_name="Code Quality",
#         score_name="code_quality",
#         files={"main.py": "...", "README.md": "..."},
#     )
# ------------------------------------------------------------------------------------


def build_file_analysis_prompt(
    metric_name: str,
    score_name: str,
    files: Dict[str, str],
    score_range: str = "[0.0, 1.0]",
) -> str:
    """Construct a structured prompt for LLM-based multi-file analysis."""

    instructions = f"""
You are an expert evaluator for the metric: "{metric_name}".

Examine the provided repository files and produce a single score in the range {score_range}.

Return ONLY a JSON object of the exact form:
{{ "{score_name}": <float {score_range}> }}
    """

    sections = {f"FILE: {fname}": content for fname, content in files.items()}

    return build_llm_prompt(
        instructions=instructions,
        sections=sections,
    )
