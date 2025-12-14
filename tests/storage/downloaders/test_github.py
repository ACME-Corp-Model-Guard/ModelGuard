import os
from pathlib import Path

import pytest
import requests
from unittest.mock import patch

from src.storage.downloaders.github import (
    FileDownloadError,
    _download_repo_tarball,
    _parse_github_url,
    download_from_github,
    fetch_github_code_metadata,
)


# =============================================================================
# _parse_github_url
# =============================================================================
def test_parse_github_url_valid():
    owner, repo = _parse_github_url("https://github.com/user/project")
    assert owner == "user"
    assert repo == "project"


def test_parse_github_url_invalid_missing_repo():
    with pytest.raises(FileDownloadError):
        _parse_github_url("https://github.com/user")  # no repo


def test_parse_github_url_invalid_format():
    # Should fail because it doesn't contain "github.com/"
    with pytest.raises(FileDownloadError):
        _parse_github_url("https://example.com/user/project")


def test_parse_github_url_strips_git_suffix():
    """Test that .git suffix is properly stripped from repository names."""
    owner, repo = _parse_github_url("https://github.com/user/project.git")
    assert owner == "user"
    assert repo == "project"  # .git should be stripped


# =============================================================================
# _download_repo_tarball
# =============================================================================
@patch("src.storage.downloaders.github._get_github_headers")
def test_download_repo_tarball_success(mock_get_headers, monkeypatch, tmp_path):
    """Test successful repo download via GitHub REST API."""

    mock_get_headers.return_value = {"Authorization": "token FAKE_TOKEN"}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            # Fake tarball content
            yield b"fake tarball data"

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())

    # Third parameter is now artifact_id, not dest_dir
    result_path = _download_repo_tarball("user", "repo", "test-artifact-id")

    assert os.path.exists(result_path)
    assert result_path.endswith(".tar.gz")
    assert result_path.startswith("/tmp/gh_test-artifact-id_")


@patch("src.storage.downloaders.github._get_github_headers")
def test_download_repo_tarball_not_found(mock_get_headers, monkeypatch, tmp_path):
    """Test handling of 404 (repository not found)."""

    mock_get_headers.return_value = {"Authorization": "token FAKE_TOKEN"}

    class FakeResponse:
        status_code = 404

        def raise_for_status(self):
            raise requests.HTTPError("404 Client Error: Not Found")

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())

    with pytest.raises(FileDownloadError, match="Failed to download repository from API"):
        # Third parameter is now artifact_id, not dest_dir
        _download_repo_tarball("user", "nonexistent", "test-artifact-id")


# =============================================================================
# download_from_github (main)
# =============================================================================
def test_download_from_github_success(monkeypatch, tmp_path):
    """Full pipeline using mocks."""
    monkeypatch.setattr(
        "src.storage.downloaders.github._parse_github_url",
        lambda url: ("user", "repo"),
    )

    def fake_download_tarball(owner: str, repo: str, artifact_id: str):
        # Create a fake tarball file in /tmp
        import tempfile

        tar_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".tar.gz", prefix=f"gh_{artifact_id}_", dir="/tmp"
        )
        tar_file.write(b"fake tarball content")
        tar_file.close()
        return tar_file.name

    monkeypatch.setattr(
        "src.storage.downloaders.github._download_repo_tarball", fake_download_tarball
    )

    result = download_from_github(
        source_url="https://github.com/user/repo",
        artifact_id="123",
        artifact_type="code",
    )

    assert result.endswith(".tar.gz")
    assert Path(result).exists()
    assert result.startswith("/tmp/gh_123_")


def test_download_from_github_wrong_type():
    with pytest.raises(FileDownloadError):
        download_from_github(
            source_url="https://github.com/user/repo",
            artifact_id="123",
            artifact_type="model",
        )


def test_download_from_github_parse_failure(monkeypatch):
    monkeypatch.setattr(
        "src.storage.downloaders.github._parse_github_url",
        lambda url: (_ for _ in ()).throw(FileDownloadError("bad url")),
    )

    with pytest.raises(FileDownloadError):
        download_from_github(
            source_url="https://github.com/user",
            artifact_id="123",
            artifact_type="code",
        )


# =============================================================================
# fetch_github_code_metadata
# =============================================================================
@patch("src.storage.downloaders.github._get_github_headers")
def test_fetch_github_code_metadata_success(mock_get_headers, monkeypatch):

    mock_get_headers.return_value = {"Authorization": "token FAKE_TOKEN"}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "name": "repo",
                "description": "desc",
                "language": "Python",
                "size": 1,
                "license": {"spdx_id": "MIT"},
                "stargazers_count": 10,
                "forks_count": 2,
                "open_issues_count": 1,
                "default_branch": "main",
                "clone_url": "https://github.com/user/repo.git",
            }

    monkeypatch.setattr("requests.get", lambda url, timeout=10: FakeResponse())

    metadata = fetch_github_code_metadata("https://github.com/user/repo")
    assert metadata["name"] == "repo"
    assert metadata["metadata"]["language"] == "Python"
    assert metadata["metadata"]["stars"] == 10


def test_fetch_github_code_metadata_invalid_url():
    with pytest.raises(FileDownloadError):
        fetch_github_code_metadata("https://example.com/notgithub")


def test_fetch_github_code_metadata_http_error(monkeypatch):
    class FakeBadResponse:
        def raise_for_status(self):
            raise requests.RequestException("oops")

    monkeypatch.setattr("requests.get", lambda url, timeout=10: FakeBadResponse())

    with pytest.raises(Exception):
        fetch_github_code_metadata("https://github.com/user/repo")
