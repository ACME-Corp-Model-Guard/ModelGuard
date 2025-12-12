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
import re
from typing import Any, Dict, List, Optional, Union

from botocore.exceptions import ClientError
from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

from src.aws.clients import get_bedrock_runtime
from src.logutil import clogger
from src.settings import BEDROCK_MODEL_ID, BEDROCK_REGION


# ====================================================================================
# CONSTANTS
# ====================================================================================

# Bedrock Titan Text Lite model: 4096 input tokens max
# Conservative limit to stay under hard limit and observed errors (4519)
MAX_INPUT_TOKENS = 3500


# ====================================================================================
# PUBLIC API - LLM INVOCATION
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

        # Log input characteristics for visibility
        estimated_input_tokens = _estimate_token_count(prompt)
        clogger.debug(
            f"[llm] Preparing request: model={model_id}, "
            f"input_tokens~{estimated_input_tokens}, max_output_tokens={max_tokens}, "
            f"temperature={temperature}"
        )

        request_body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
            },
        }

        clogger.debug(
            f"[llm] Invoking Bedrock model '{model_id}'"
            f" with request body: {json.dumps(request_body)}"
        )

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
        )

        raw_bytes = response["body"].read()
        raw_text = raw_bytes.decode("utf-8")

        if not raw_text:
            clogger.error("[llm] Empty raw response body from Bedrock")
            clogger.debug(
                f"[llm] Request summary: input_tokens~{estimated_input_tokens}, "
                f"max_output_tokens={max_tokens}, temperature={temperature}"
            )
            return None

        parsed = json.loads(raw_text)
        # Defensive parsing with visibility
        try:
            content = parsed["results"][0]["outputText"]
        except (KeyError, IndexError, TypeError):
            clogger.error(
                "[llm] Unexpected response schema; 'results[0].outputText' not found"
            )
            clogger.debug(f"[llm] Raw parsed keys: {list(parsed.keys())}")
            clogger.debug(f"[llm] Raw text (first 500 chars):\n{raw_text[:500]}")
            return None

        if return_json:
            return _extract_json_from_response(content)

        return content

    except (ClientError, KeyError, json.JSONDecodeError) as e:
        clogger.error(f"[llm] Bedrock request failed: {e}")
        # Provide more context where possible
        clogger.debug(
            f"[llm] Failure context: "
            f"model={model_id}, input_tokens~{_estimate_token_count(prompt)}, "
            f"max_output_tokens={max_tokens}, temperature={temperature}"
        )
        return None


# ====================================================================================
# PUBLIC API - PROMPT BUILDERS
# ====================================================================================
# GENERIC PROMPT BUILDER
#
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
    important_terms: Optional[List[str]] = None,
    max_input_tokens: Optional[int] = None,
) -> str:
    """Construct a structured prompt with smart token budgeting.

    Strategy:
    - Preserve instructions and metric description intact
    - Allocate per-section budgets proportional to size (with min floor)
    - Trim from END of each section to preserve headers
    - Prefer lines matching important_terms before adding tail lines
    - Respect max_input_tokens override or use MAX_INPUT_TOKENS
    """

    token_budget = max_input_tokens or MAX_INPUT_TOKENS
    important = important_terms or []

    # Assemble header (always preserved)
    header_parts: List[str] = [instructions.strip() + "\n\n"]
    if metric_description:
        header_parts.append("=== Metric Description ===\n")
        header_parts.append(metric_description.strip() + "\n\n")
    header_text = "\n".join(header_parts)

    section_items = list(sections.items()) if sections else []

    # No sections: just header within budget
    if not section_items:
        final = _truncate_to_token_limit(header_text, max_tokens=token_budget)
        clogger.debug(
            f"[llm_prompt_builder] Built prompt with 1 block, "
            f"estimated {_estimate_token_count(final)} tokens"
        )
        return final

    # Build raw sections
    raw_sections = [f"=== {title} ===\n{content}\n" for title, content in section_items]

    header_tokens = _estimate_token_count(header_text)
    remaining = max(1, token_budget - header_tokens)

    section_tokens = [max(1, _estimate_token_count(s)) for s in raw_sections]
    total_tokens = sum(section_tokens)

    # If sections fit, finalize directly
    if total_tokens <= remaining:
        prompt = header_text + "\n" + "\n".join(raw_sections)
        prompt = _truncate_to_token_limit(prompt, max_tokens=token_budget)
        clogger.debug(
            f"[llm_prompt_builder] Built prompt with {1 + len(raw_sections)} block(s), "
            f"estimated {_estimate_token_count(prompt)} tokens"
        )
        return prompt

    # Otherwise, allocate budgets and trim each section
    # Dynamic floor prevents overallocation with many sections
    min_floor = max(10, min(50, remaining // max(1, len(section_items))))
    total = max(1, sum(section_tokens))
    provisional = [max(min_floor, int((t / total) * remaining)) for t in section_tokens]
    scale = remaining / max(1, sum(provisional))
    budgets = [max(min_floor, int(p * scale)) for p in provisional]

    # Trim each section to its budget, preserving important lines
    trimmed_sections = [
        _trim_section_to_budget(s, b, important) for s, b in zip(raw_sections, budgets)
    ]

    prompt = header_text + "\n" + "\n".join(trimmed_sections)
    prompt = _truncate_to_token_limit(prompt, max_tokens=token_budget)
    clogger.debug(
        f"[llm_prompt_builder] Built prompt with {1 + len(trimmed_sections)} block(s), "
        f"estimated {_estimate_token_count(prompt)} tokens"
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
    fields_json: Dict[str, Optional[str]] = {}
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
        response: Result from ask_llm(..., return_json=True) OR raw string
        field: Name of the score field expected inside the JSON object

    Returns:
        float score if valid, otherwise None
    """

    # If response is a string, try to extract JSON first
    if isinstance(response, str):
        response = _extract_json_from_response(response)
        if response is None:
            clogger.error("[llm] Failed to parse JSON from string response")
            return None

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


# ====================================================================================
# PRIVATE HELPERS - PROMPT BUDGETING
# ====================================================================================


def _trim_section_to_budget(
    text: str, token_budget: int, important_terms: List[str]
) -> str:
    """Trim section to budget: keep important lines + tail lines, preserving original order."""
    if _estimate_token_count(text) <= token_budget:
        return text

    lines = text.splitlines()

    # Validate and compile regex patterns
    patterns = []
    for p in important_terms:
        try:
            patterns.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            clogger.warning(f"[llm] Invalid regex pattern '{p}': {e}. Skipping.")
            continue

    def is_important(line: str) -> bool:
        return any(p.search(line) for p in patterns)

    # Collect important line indices
    important_indices = {i for i, ln in enumerate(lines) if is_important(ln)}

    # Start with important lines and track tokens incrementally
    selected_indices = set(important_indices)
    running_tokens = _estimate_token_count(
        "\n".join(lines[i] for i in sorted(selected_indices))
    )

    # Add tail lines from the end until budget would be exceeded
    for i in range(len(lines) - 1, -1, -1):
        if i not in selected_indices:
            # Check BEFORE adding to avoid exceeding budget
            line_tokens = _estimate_token_count(lines[i])
            if running_tokens + line_tokens + 1 > token_budget:  # +1 for newline
                continue

            selected_indices.add(i)
            running_tokens += line_tokens + 1

    # Extract lines in original order
    final_indices = sorted(selected_indices)
    trimmed_lines = [lines[i] for i in final_indices]
    return "\n".join(trimmed_lines)


# ====================================================================================
# PRIVATE HELPERS - JSON EXTRACTION
# ====================================================================================


def _extract_json_from_response(content: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM response, even if embedded in explanatory text.

    Tries multiple strategies:
    1. Direct JSON parsing
    2. Extract JSON block using regex
    3. Extract first {...} or [...] structure

    Returns parsed JSON dict on success, None on failure.
    """

    if not content or not isinstance(content, str):
        clogger.error("[llm] Invalid response content (not a string)")
        return None

    # Strategy 1: Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract JSON code block (```json ... ```)
    match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Extract first {...} structure
    match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # All strategies failed
    clogger.error("[llm] Failed to extract JSON from LLM output")
    clogger.debug(f"[llm] Raw output (first 500 chars):\n{content[:500]}")
    return None


# ====================================================================================
# PRIVATE HELPERS - TOKEN MANAGEMENT
# ====================================================================================


def _estimate_token_count(text: str) -> int:
    """Rough estimate of token count (1 token ≈ 4 characters for English)."""
    return max(1, len(text) // 4)


def _truncate_to_token_limit(text: str, max_tokens: int = MAX_INPUT_TOKENS) -> str:
    """
    Truncate text to fit within token limit.

    Uses a rough heuristic: 1 token ≈ 4 characters.
    Adds ellipsis if truncation occurs.
    """
    estimated = _estimate_token_count(text)

    if estimated <= max_tokens:
        return text

    # Calculate approximate character limit
    char_limit = max_tokens * 4
    truncated = text[:char_limit].rstrip()

    clogger.warning(
        f"[llm] Truncating prompt to fit token limit "
        f"({estimated} → {_estimate_token_count(truncated + '...')} estimated tokens)"
    )

    return truncated + "..."
