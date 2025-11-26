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
    # Fake Bedrock response structure
    response_json = {
        "content": [{"text": "Hello world"}]
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
        "content": [{"text": '{"score": 0.95}'}]
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
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: b"{not json")
    }

    result = llm.ask_llm("prompt")
    assert result is None


def test_ask_llm_missing_keys(mock_bedrock):
    """
    ask_llm should handle KeyError if the Bedrock response is missing expected fields.
    """
    mock_bedrock.invoke_model.return_value = {
        "body": MagicMock(read=lambda: json.dumps({}).encode("utf-8"))
    }

    result = llm.ask_llm("prompt")
    assert result is None


def test_ask_llm_client_error(mock_bedrock):
    """
    ask_llm should return None if Bedrock raises ClientError.
    """
    from botocore.exceptions import ClientError

    mock_bedrock.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "Boom"}}, "InvokeModel"
    )

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
    files = {
        "a.py": "print('a')",
        "README.md": "docs"
    }

    prompt = llm.build_file_analysis_prompt(
        metric_name="Code Quality",
        score_name="code_quality",
        files=files,
    )

    assert "Code Quality" in prompt
    assert "code_quality" in prompt
    assert '"code_quality": <float [0.0, 1.0]>' in prompt

    assert "=== FILE: a.py ===" in prompt
    assert "print('a')" in prompt
    assert "=== FILE: README.md ===" in prompt
    assert "docs" in prompt
