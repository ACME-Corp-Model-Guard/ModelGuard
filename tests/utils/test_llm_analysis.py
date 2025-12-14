import json
from unittest.mock import MagicMock

import pytest

import src.utils.llm_analysis as llm


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture
def mock_bedrock(monkeypatch):
    """
    Patch get_bedrock_runtime() so ask_llm() uses a mock client.
    """
    mock_client = MagicMock()
    monkeypatch.setattr(llm, "get_bedrock_runtime", lambda region=None: mock_client)
    return mock_client


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """
    Ensure required settings exist.
    """
    monkeypatch.setattr(llm, "BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(llm, "BEDROCK_REGION", "us-east-1")


# =====================================================================
# ask_llm() — success cases
# =====================================================================


def test_ask_llm_returns_string(mock_bedrock):
    """
    ask_llm should extract the model text content and return it.
    """
    # Fake Amazon Nova response structure
    response_json = {
        "output": {"message": {"content": [{"text": "Hello world"}], "role": "assistant"}},
        "stopReason": "end_turn",
    }

    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps(response_json).encode("utf-8"))
    }

    result = llm.ask_llm("test prompt")

    assert result == "Hello world"
    mock_bedrock.invoke_model.assert_called_once()


def test_ask_llm_returns_json_parsed(mock_bedrock):
    """
    ask_llm(return_json=True) should JSON-decode the model output.
    """
    response_json = {
        "output": {"message": {"content": [{"text": '{"score": 0.95}'}], "role": "assistant"}},
        "stopReason": "end_turn",
    }

    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps(response_json).encode("utf-8"))
    }

    result = llm.ask_llm("prompt", return_json=True)
    assert result == {"score": 0.95}


# =====================================================================
# ask_llm() — error & malformed cases
# =====================================================================


def test_ask_llm_malformed_body(mock_bedrock):
    """
    ask_llm should handle json.JSONDecodeError on the outer response.
    """
    mock_bedrock.invoke_model.return_value = {"body": MagicMock(read=lambda: b"{not json")}

    result = llm.ask_llm("prompt")
    assert result is None


def test_ask_llm_missing_keys(mock_bedrock):
    """
    ask_llm should handle KeyError if the Bedrock response is missing expected fields.
    """
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps({"stopReason": "end_turn"}).encode("utf-8"))
    }

    result = llm.ask_llm("prompt")
    assert result is None


def test_ask_llm_client_error(mock_bedrock):
    """
    ask_llm should return None if Bedrock raises ClientError.
    """
    from botocore.exceptions import ClientError

    mock_bedrock.invoke_model.side_effect = ClientError({"Error": {"Code": "Boom"}}, "InvokeModel")

    result = llm.ask_llm("prompt")
    assert result is None


# =====================================================================
# build_llm_prompt()
# =====================================================================


def test_build_llm_prompt_with_sections():
    prompt = llm.build_llm_prompt(
        instructions="Analyze:",
        sections={"file.py": "print('hi')", "README.md": "docs"},
    )

    # Instructions appear first
    assert prompt.startswith("Analyze:")

    # Both sections included
    assert "=== file.py ===" in prompt
    assert "print('hi')" in prompt
    assert "=== README.md ===" in prompt


def test_build_llm_prompt_without_sections():
    prompt = llm.build_llm_prompt("Hello", sections=None)
    assert prompt.strip() == "Hello"


# =====================================================================
# build_file_analysis_prompt()
# =====================================================================


def test_build_file_analysis_prompt_basic():
    files = {"a.py": "print('a')", "README.md": "docs"}

    prompt = llm.build_file_analysis_prompt(
        metric_name="Code Quality",
        score_name="code_quality",
        files=files,
    )

    assert "Code Quality" in prompt
    assert "code_quality" in prompt

    assert "=== FILE: a.py ===" in prompt
    assert "print('a')" in prompt
    assert "=== FILE: README.md ===" in prompt
    assert "docs" in prompt


def test_build_file_analysis_prompt_with_description():
    """Metric description should be included in prompt."""
    files = {"test.py": "code"}
    prompt = llm.build_file_analysis_prompt(
        metric_name="Test Metric",
        score_name="test_score",
        files=files,
        metric_description="This metric evaluates test coverage.",
    )
    assert "This metric evaluates test coverage" in prompt


# =====================================================================
# build_extract_fields_from_files_prompt()
# =====================================================================


def test_build_extract_fields_from_files_prompt_basic():
    """Should build prompt with fields and files."""
    fields = {"dataset_name": None, "license": None}
    files = {"README.md": "Uses dataset: MNIST\nLicense: MIT"}

    prompt = llm.build_extract_fields_from_files_prompt(fields=fields, files=files)

    assert "dataset_name" in prompt
    assert "license" in prompt
    assert "README.md" in prompt
    assert "MNIST" in prompt


def test_build_extract_fields_from_files_prompt_with_values():
    """Fields with existing values should show them."""
    fields = {"dataset_name": "existing_value"}
    files = {"test.txt": "content"}

    prompt = llm.build_extract_fields_from_files_prompt(fields=fields, files=files)

    assert "existing_value" in prompt


# =====================================================================
# extract_llm_score_field()
# =====================================================================


def test_extract_llm_score_field_from_dict():
    """Should extract float from dict response."""
    response = {"code_quality": 0.85}
    result = llm.extract_llm_score_field(response, "code_quality")
    assert result == 0.85


def test_extract_llm_score_field_from_int():
    """Should convert int to float."""
    response = {"score": 1}
    result = llm.extract_llm_score_field(response, "score")
    assert result == 1.0


def test_extract_llm_score_field_from_string():
    """Should parse numeric string."""
    response = {"score": "0.75"}
    result = llm.extract_llm_score_field(response, "score")
    assert result == 0.75


def test_extract_llm_score_field_missing_field():
    """Should return None if field not in response."""
    response = {"other_field": 0.5}
    result = llm.extract_llm_score_field(response, "score")
    assert result is None


def test_extract_llm_score_field_non_dict():
    """Should return None for non-dict response."""
    result = llm.extract_llm_score_field("not a dict", "score")
    assert result is None


def test_extract_llm_score_field_non_numeric_value():
    """Should return None for non-numeric value."""
    response = {"score": "not a number"}
    result = llm.extract_llm_score_field(response, "score")
    assert result is None


def test_extract_llm_score_field_from_json_string():
    """Should extract from JSON string response."""
    response = '{"score": 0.9}'
    result = llm.extract_llm_score_field(response, "score")
    assert result == 0.9


def test_extract_llm_score_field_from_embedded_json():
    """Should extract from embedded JSON in text."""
    response = 'Here is the result: {"score": 0.8}'
    result = llm.extract_llm_score_field(response, "score")
    assert result == 0.8


def test_extract_llm_score_field_invalid_json_string():
    """Should return None for invalid JSON string."""
    result = llm.extract_llm_score_field("not valid json at all", "score")
    assert result is None


def test_extract_llm_score_field_none_response():
    """Should return None for None response."""
    result = llm.extract_llm_score_field(None, "score")
    assert result is None


# =====================================================================
# Private helper tests - _sanitize_json_value
# =====================================================================


def test_sanitize_json_value_none():
    """None should remain None."""
    assert llm._sanitize_json_value(None) is None


def test_sanitize_json_value_null_string():
    """String 'null' should become None."""
    assert llm._sanitize_json_value("null") is None
    assert llm._sanitize_json_value("NULL") is None
    assert llm._sanitize_json_value("None") is None
    assert llm._sanitize_json_value("n/a") is None
    assert llm._sanitize_json_value("") is None


def test_sanitize_json_value_placeholder():
    """Placeholder values should become None."""
    assert llm._sanitize_json_value("PUT VALUE HERE") is None
    assert llm._sanitize_json_value("put value here please") is None


def test_sanitize_json_value_valid_string():
    """Valid strings should be preserved."""
    assert llm._sanitize_json_value("hello") == "hello"
    assert llm._sanitize_json_value("  trimmed  ") == "trimmed"


def test_sanitize_json_value_dict():
    """Dicts should be recursively sanitized."""
    result = llm._sanitize_json_value({"key": "null", "other": "value"})
    assert result == {"key": None, "other": "value"}


def test_sanitize_json_value_list():
    """Lists should be recursively sanitized."""
    result = llm._sanitize_json_value(["value", "null", "n/a"])
    assert result == ["value", None, None]


def test_sanitize_json_value_numbers():
    """Numbers should be preserved."""
    assert llm._sanitize_json_value(42) == 42
    assert llm._sanitize_json_value(3.14) == 3.14


def test_sanitize_json_value_bool():
    """Booleans should be preserved."""
    assert llm._sanitize_json_value(True) is True
    assert llm._sanitize_json_value(False) is False


# =====================================================================
# Private helper tests - _extract_json_from_response
# =====================================================================


def test_extract_json_direct_parse():
    """Should parse direct JSON."""
    result = llm._extract_json_from_response('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_code_block():
    """Should extract from markdown code block."""
    content = 'Here is the result:\n```json\n{"score": 0.5}\n```'
    result = llm._extract_json_from_response(content)
    assert result == {"score": 0.5}


def test_extract_json_embedded():
    """Should extract embedded JSON object."""
    content = 'The analysis shows: {"result": "good"} and that\'s all.'
    result = llm._extract_json_from_response(content)
    assert result == {"result": "good"}


def test_extract_json_non_string():
    """Should return None for non-string input."""
    result = llm._extract_json_from_response(123)
    assert result is None


def test_extract_json_empty_string():
    """Should return None for empty string."""
    result = llm._extract_json_from_response("")
    assert result is None
    result = llm._extract_json_from_response("   ")
    assert result is None


def test_extract_json_no_json():
    """Should return None when no JSON found."""
    result = llm._extract_json_from_response("just plain text with no json")
    assert result is None


# =====================================================================
# Private helper tests - _estimate_token_count
# =====================================================================


def test_estimate_token_count_basic():
    """Should estimate tokens based on character count."""
    # CHARS_PER_TOKEN is 3, so 9 chars = 3 tokens
    result = llm._estimate_token_count("123456789")
    assert result == 3


def test_estimate_token_count_minimum():
    """Should return at least 1 token."""
    result = llm._estimate_token_count("")
    assert result == 1
    result = llm._estimate_token_count("a")
    assert result == 1


# =====================================================================
# Private helper tests - _truncate_to_token_limit
# =====================================================================


def test_truncate_to_token_limit_under_budget():
    """Text under limit should not be truncated."""
    text = "short text"
    result = llm._truncate_to_token_limit(text, max_tokens=1000)
    assert result == text


def test_truncate_to_token_limit_over_budget():
    """Text over limit should be truncated with ellipsis."""
    # Make a long text that exceeds the budget
    text = "x" * 100
    result = llm._truncate_to_token_limit(text, max_tokens=10)
    assert result.endswith("...")
    assert len(result) < len(text)


# =====================================================================
# ask_llm() — additional edge cases
# =====================================================================


def test_ask_llm_empty_response_body(mock_bedrock):
    """ask_llm should handle empty response body."""
    mock_bedrock.invoke_model.return_value = {"body": MagicMock(read=lambda: b"")}
    result = llm.ask_llm("prompt")
    assert result is None


def test_ask_llm_return_json_invalid(mock_bedrock):
    """ask_llm(return_json=True) should return None for invalid JSON."""
    response_json = {
        "output": {"message": {"content": [{"text": "not valid json"}], "role": "assistant"}},
        "stopReason": "end_turn",
    }
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps(response_json).encode("utf-8"))
    }
    result = llm.ask_llm("prompt", return_json=True)
    assert result is None


def test_ask_llm_json_with_markdown(mock_bedrock):
    """ask_llm should extract JSON from markdown code blocks."""
    response_json = {
        "output": {
            "message": {
                "content": [{"text": '```json\n{"score": 0.7}\n```'}],
                "role": "assistant",
            }
        },
        "stopReason": "end_turn",
    }
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps(response_json).encode("utf-8"))
    }
    result = llm.ask_llm("prompt", return_json=True)
    assert result == {"score": 0.7}


def test_ask_llm_short_response(mock_bedrock):
    """ask_llm should handle suspiciously short responses."""
    response_json = {
        "output": {"message": {"content": [{"text": "Hi"}], "role": "assistant"}},
        "stopReason": "end_turn",
    }
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps(response_json).encode("utf-8"))
    }
    # Short response should still be returned
    result = llm.ask_llm("prompt")
    assert result == "Hi"


# =====================================================================
# build_llm_prompt() - Token Budgeting
# =====================================================================


def test_build_llm_prompt_exceeds_token_budget():
    """Prompt sections exceeding token budget should be trimmed."""
    # Create sections that exceed the budget
    large_content = "x" * 50000  # Very large content

    prompt = llm.build_llm_prompt(
        instructions="Analyze:",
        sections={"large.txt": large_content},
    )

    # Should be truncated
    assert len(prompt) < len(large_content)
    assert "Analyze:" in prompt


def test_build_llm_prompt_with_important_terms():
    """Important terms should be preserved when trimming."""
    # Create content with important lines
    lines = ["line 1", "IMPORTANT: keep this", "line 3", "CRITICAL: also keep", "line 5"]
    content = "\n".join(lines * 100)  # Repeat to make it large

    prompt = llm.build_llm_prompt(
        instructions="Analyze:",
        sections={"test.txt": content},
        important_terms=["IMPORTANT", "CRITICAL"],
    )

    assert "Analyze:" in prompt


def test_build_llm_prompt_multiple_large_sections():
    """Multiple large sections should all be trimmed proportionally."""
    large_content = "x" * 20000

    prompt = llm.build_llm_prompt(
        instructions="Analyze:",
        sections={
            "file1.txt": large_content,
            "file2.txt": large_content,
            "file3.txt": large_content,
        },
    )

    # All sections should be present but trimmed
    assert "file1.txt" in prompt
    assert "file2.txt" in prompt
    assert "file3.txt" in prompt


# =====================================================================
# _trim_section_to_budget()
# =====================================================================


def test_trim_section_under_budget():
    """Section under budget should not be trimmed."""
    text = "short text"
    result = llm._trim_section_to_budget(text, token_budget=1000, important_terms=[])
    assert result == text


def test_trim_section_over_budget():
    """Section over budget should be trimmed."""
    text = "x" * 1000
    result = llm._trim_section_to_budget(text, token_budget=10, important_terms=[])
    assert len(result) < len(text)


def test_trim_section_preserves_important_lines():
    """Important lines should be preserved when trimming."""
    lines = ["line 1", "IMPORTANT: keep", "line 3", "line 4", "line 5"]
    text = "\n".join(lines * 50)  # Make it large

    result = llm._trim_section_to_budget(text, token_budget=50, important_terms=["IMPORTANT"])

    # Important line should be kept
    assert "IMPORTANT" in result


def test_trim_section_invalid_regex():
    """Invalid regex patterns should be skipped."""
    text = "test content\n" * 100
    # Invalid regex pattern with unclosed bracket
    result = llm._trim_section_to_budget(text, token_budget=50, important_terms=["[invalid"])
    # Should not crash, just skip the invalid pattern
    assert len(result) > 0


def test_trim_section_important_exceeds_budget():
    """When important lines exceed budget, should truncate."""
    # Many important lines
    lines = [f"IMPORTANT line {i}" for i in range(100)]
    text = "\n".join(lines)

    result = llm._trim_section_to_budget(text, token_budget=20, important_terms=["IMPORTANT"])

    # Should be truncated
    assert len(result) < len(text)


# =====================================================================
# _extract_json_from_response() - Additional cases
# =====================================================================


def test_extract_json_code_block_without_json_label():
    """Should extract from code block without 'json' label."""
    content = '```\n{"result": "value"}\n```'
    result = llm._extract_json_from_response(content)
    assert result == {"result": "value"}


def test_extract_json_only_invalid_code_block():
    """Code block with invalid JSON and no fallback returns None."""
    # Only invalid JSON in code block, nothing else valid
    content = "```json\n{invalid json}\n```"
    result = llm._extract_json_from_response(content)
    # Cannot extract valid JSON
    assert result is None


def test_extract_json_invalid_embedded():
    """Invalid embedded JSON should return None."""
    content = "Here is result: {not: valid: json} and nothing else"
    result = llm._extract_json_from_response(content)
    assert result is None
