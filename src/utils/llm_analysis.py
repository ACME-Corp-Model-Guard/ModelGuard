"""
LLM analysis utilities using AWS Bedrock Runtime.

Provides:
- ask_llm(): unified function for Bedrock inference
- build_llm_prompt(): generic structured prompt builder
- build_file_analysis_prompt(): helper for metrics analyzing code/dataset files
- extract_llm_score_field(): safely extract a numeric score field from LLM JSON output
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from botocore.exceptions import ClientError
from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

from src.aws.clients import get_bedrock_runtime
from src.logutil import clogger
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
    temperature: float = 0.2,
) -> Optional[Union[str, Dict[str, Any]]]:
    """Invoke a Bedrock LLM and return text or parsed JSON."""

    model_id = BEDROCK_MODEL_ID

    try:
        client: BedrockRuntimeClient = get_bedrock_runtime(region=BEDROCK_REGION)

        request_body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
            },
        }

        clogger.debug(f"[llm] Invoking Bedrock model '{model_id}'")

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
        )

        raw_bytes = response["body"].read()
        raw_text = raw_bytes.decode("utf-8")

        parsed = json.loads(raw_text)
        content = parsed["results"][0]["outputText"]

        if return_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                clogger.error("[llm] Failed to decode JSON from LLM output")
                clogger.debug(f"[llm] Raw output:\n{content}")
                return None

        return content

    except (ClientError, KeyError, json.JSONDecodeError) as e:
        clogger.error(f"[llm] Bedrock request failed: {e}")
        return None


# ====================================================================================
# GENERIC PROMPT BUILDER
# ====================================================================================
# Build a structured multi-section prompt suitable for LLM evaluation.
#
# This helper:
#   1. Inserts a main instruction block
#   2. Optionally inserts a "Metric Description" block
#   3. Appends one or more titled sections
#   4. Produces a consistent multi-block prompt format
#
# Useful for:
#   - Code-quality analysis
#   - Dataset-quality analysis
#   - Any metric using LLM-based static review
# ------------------------------------------------------------------------------------


def build_llm_prompt(
    instructions: str,
    sections: Optional[Dict[str, str]] = None,
    metric_description: Optional[str] = None,
) -> str:
    """Construct a structured prompt with instructions, optional metric description,
    and sectioned content blocks."""

    parts: List[str] = []

    # Instructions
    parts.append(instructions.strip() + "\n\n")

    # Optional metric description
    if metric_description:
        parts.append("=== Metric Description ===\n")
        parts.append(metric_description.strip() + "\n\n")

    # Section blocks
    if sections:
        for title, content in sections.items():
            parts.append(f"=== {title} ===\n")
            parts.append(content)
            parts.append("\n")

    prompt = "\n".join(parts)

    clogger.debug(
        f"[llm_prompt_builder] Built prompt with "
        f"{1 + (len(sections) if sections else 0) + (1 if metric_description else 0)} block(s)"
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
#   4. Optionally inserts a metric description block
# ------------------------------------------------------------------------------------


def build_file_analysis_prompt(
    metric_name: str,
    score_name: str,
    files: Dict[str, str],
    score_range: str = "[0.0, 1.0]",
    metric_description: Optional[str] = None,
) -> str:
    """Construct a structured prompt for LLM-based multi-file analysis with an
    optional detailed metric description."""

    instructions = f"""
You are an expert evaluator for the metric: "{metric_name}".

Examine the provided repository files and produce a single score in the range {score_range}.

Return ONLY a JSON object of the exact form:
{{ "{score_name}": <float {score_range}> }}
    """.strip()

    sections = {f"FILE: {fname}": content for fname, content in files.items()}

    return build_llm_prompt(
        instructions=instructions,
        sections=sections,
        metric_description=metric_description,
    )


# ====================================================================================
# EXTRACT FIELDS FROM FILES PROMPT BUILDER
# ====================================================================================
# Build a prompt that defines what field to extract from a set of files
#
# This helper:
#   1. Defines extraction instructions
#   2. Enforces strict JSON output (e.g., {"FIELD": "VALUE"})
#   3. Adds each provided file as a separate prompt section
#
# Usage:
#     prompt = build_extract_fields_from_files_prompt(
#         fields=["field1", "field2"],
#         files={"main.py": "...", "README.md": "..."},
#     )
# ------------------------------------------------------------------------------------


def build_extract_fields_from_files_prompt(
    fields: List[str],
    files: Dict[str, str],
) -> str:
    """Construct a structured prompt for extracting fields from files."""

    # Convert list to json, with value = PUT VALUE HERE
    fields_json: Dict[str, str | None] = {}
    for item in fields:
        fields_json[item] = "PUT VALUE HERE"

    instructions = f"""
Examine the provided repository files and fill in the value for the
following fields: {json.dumps(fields_json)}.
Include only one value per field, even if it appears in multiple files.

Return ONLY a JSON object of the exact form:
{{ "FIELD": "VALUE" }}
    """

    sections = {f"FILE: {fname}": content for fname, content in files.items()}

    return build_llm_prompt(
        instructions=instructions,
        sections=sections,
    )


# ====================================================================================
# JSON SCORE FIELD EXTRACTION
# ====================================================================================
# Safely extract a numeric score from an LLM JSON response.
#
# This helper:
#   1. Validates response is a dict
#   2. Ensures the score field exists
#   3. Ensures the value is numeric or convertible to float
#   4. Returns the float on success or None on failure
#
# Used by all LLM-based metrics (e.g., code quality, dataset quality).
# ------------------------------------------------------------------------------------


def extract_llm_score_field(
    response: Any,
    field: str,
) -> Optional[float]:
    """
    Safely extract a numeric score field from an LLM JSON response.

    Args:
        response: Result from ask_llm(..., return_json=True)
        field: Name of the score field expected inside the JSON object

    Returns:
        float score if valid, otherwise None
    """

    # Must be dictionary-shaped
    if not isinstance(response, dict):
        return None

    # Must contain the field
    if field not in response:
        return None

    value = response[field]

    # Already numeric
    if isinstance(value, (int, float)):
        return float(value)

    # Attempt to parse numeric strings
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
