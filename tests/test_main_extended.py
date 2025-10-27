"""
Additional tests for main module.
"""

import os
import tempfile
from time import perf_counter
from unittest import mock

from src.main import _early_env_exits, _lat_ms, _print_ndjson, main


def test_lat_ms():
    """Test the _lat_ms function."""
    # Test with a small time difference
    assert _lat_ms(perf_counter() - 0.001) >= 1
    # Test with a larger time difference
    assert _lat_ms(perf_counter() - 1.5) >= 1


def test_print_ndjson(capsys):
    """Test _print_ndjson function."""
    rows = [{"name": "test1", "value": 1}, {"name": "test2", "value": 2}]
    _print_ndjson(rows)

    captured = capsys.readouterr()
    assert '{"name":"test1","value":1}' in captured.out
    assert '{"name":"test2","value":2}' in captured.out


def test_print_ndjson_empty_list(capsys):
    """Test _print_ndjson with an empty list."""
    _print_ndjson([])
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_invalid_args(monkeypatch):
    """Test main function with invalid arguments."""
    # Patch GITHUB_TOKEN so token check does not
    # interfere with argument/file checks
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")

    # Test with no arguments
    assert main([]) == 2

    # Test with non-existent file
    assert main(["program", "/tmp/this_file_should_not_exist_123456789"]) == 2


def test_main_with_valid_file(monkeypatch):
    """Test main function with a valid file."""
    # Patch GITHUB_TOKEN so token check does not interfere
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")
    # Create a temporary file with URLs
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("https://example.com\n")
        tmp.flush()
        tmp_path = tmp.name

    # Mock compute_all to return a predefined result
    with mock.patch("src.main.compute_all") as mock_compute:
        mock_compute.return_value = [{"url": "https://example.com"}]

        # Mock _print_ndjson to avoid actual printing
        with mock.patch("src.main._print_ndjson"):
            result = main(["program", tmp_path])
            assert result == 0

    # Clean up
    os.unlink(tmp_path)


def test_main_with_empty_file(monkeypatch, capsys):
    """Test main with an empty file."""
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = main(["program", tmp_path])
        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
    finally:
        os.unlink(tmp_path)


def test_main_with_comments_only_file(monkeypatch, capsys):
    """Test main with a file containing only comments and blank lines."""
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp.write("# comment\n\n# another comment\n\n")
        tmp.flush()
        tmp_path = tmp.name
    try:
        result = main(["program", tmp_path])
        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
    finally:
        os.unlink(tmp_path)


def test_lat_ms_zero_and_negative():
    """Test _lat_ms with zero and negative time differences."""
    now = perf_counter()
    assert _lat_ms(now) == 1  # zero difference
    assert _lat_ms(now + 1) == 1  # negative difference (should clamp to 1)


def test_print_ndjson_non_serializable():
    """Test _print_ndjson with a non-serializable object."""

    class NonSerializable:
        pass

    try:
        _print_ndjson([NonSerializable()])
    except TypeError:
        pass
    else:
        assert False, "TypeError not raised for non-serializable object"


def test_main_file_permission_error(monkeypatch, capsys):
    """Test main with a file that cannot be read (permission denied)."""
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    os.chmod(tmp_path, 0)  # Remove all permissions
    try:
        result = main(["program", tmp_path])
        assert result in (1, 2)  # Depending on where the error is caught
        captured = capsys.readouterr()
        assert (
            "Error" in captured.err
            or "Permission" in captured.err
            or "denied" in captured.err
        )
    finally:
        os.chmod(tmp_path, 0o600)
        os.unlink(tmp_path)


def test_main_with_exception():
    """Test main function when compute_all raises an exception."""
    # Create a temporary file with URLs
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("https://example.com\n")
        tmp.flush()
        tmp_path = tmp.name

    # Mock compute_all to raise an exception
    with mock.patch("src.main.compute_all", side_effect=Exception("Test error")):
        result = main(["program", tmp_path])
        assert result == 1

    # Clean up
    os.unlink(tmp_path)


def test_early_env_exits_with_valid_token(monkeypatch):
    """Test _early_env_exits with a valid GitHub token."""
    monkeypatch.setenv("GITHUB_TOKEN", "valid_token")
    assert _early_env_exits() == 0
    # No need to pop the token, monkeypatch handles it


def test_early_env_exits_with_invalid_token(monkeypatch, capsys):
    """Test _early_env_exits with an invalid GitHub token."""
    monkeypatch.setenv("GITHUB_TOKEN", "INVALID")
    monkeypatch.setenv("FORCE_GITHUB_TOKEN_VALIDATION", "1")

    # Mock requests.get to simulate invalid token response
    import requests

    class MockResp:
        status_code = 401

    monkeypatch.setattr(requests, "get", lambda *a, **kw: MockResp())
    result = _early_env_exits()
    assert result == 1

    captured = capsys.readouterr()
    # Only check stderr, not stdout
    assert "Error: Invalid GitHub token" in captured.err

    # No need to pop the token, monkeypatch handles it


def test_early_env_exits_with_missing_token(monkeypatch, capsys):
    """Test _early_env_exits when GITHUB_TOKEN is missing."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("FORCE_GITHUB_TOKEN_VALIDATION", "1")
    result = _early_env_exits()
    assert result == 1
    captured = capsys.readouterr()
    assert "Missing GITHUB_TOKEN environment variable" in captured.err
