import tempfile
from pathlib import Path

import pytest
import requests

from src.storage.downloaders.github import (
    FileDownloadError,
    _cleanup_temp_dir,
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


def test_parse_github_url_with_git_suffix():
    """Test parsing URLs with .git suffix."""
    owner, repo = _parse_github_url("https://github.com/user/project.git")
    assert owner == "user"
    assert repo == "project"  # .git stripped


def test_parse_github_url_with_trailing_slash():
    """Test parsing URLs with trailing slash."""
    owner, repo = _parse_github_url("https://github.com/user/project/")
    assert owner == "user"
    assert repo == "project"


def test_parse_github_url_with_git_suffix_and_slash():
    """Test parsing URLs with both .git suffix and trailing slash."""
    owner, repo = _parse_github_url("https://github.com/user/project.git/")
    assert owner == "user"
    assert repo == "project"


def test_parse_github_url_invalid_missing_repo():
    with pytest.raises(FileDownloadError):
        _parse_github_url("https://github.com/user")  # no repo


def test_parse_github_url_invalid_format():
    # Should fail because it doesn't contain "github.com/"
    with pytest.raises(FileDownloadError):
        _parse_github_url("https://example.com/user/project")


# =============================================================================
# _cleanup_temp_dir
# =============================================================================
def test_cleanup_temp_dir_existing(tmp_path):
    temp = tmp_path / "tempdir"
    temp.mkdir()
    assert temp.exists()

    _cleanup_temp_dir(temp.as_posix())
    assert not temp.exists()


def test_cleanup_temp_dir_nonexistent():
    _cleanup_temp_dir("/path/that/does/not/exist")


# =============================================================================
# download_from_github (main)
# =============================================================================
def test_download_from_github_success(monkeypatch, tmp_path):
    """Full pipeline using GitHub API approach with mocks."""

    # Mock requests.get for GitHub API call
    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            # Fake tar.gz content chunks
            return [b"fake", b"tar", b"content"]

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: FakeResponse())

    # Mock tempfile.NamedTemporaryFile
    def fake_namedtempfile(**kwargs):
        tar_path = tmp_path / "fake.tar.gz"
        tar_path.touch()  # Create empty file
        return type("TempFile", (), {"name": str(tar_path)})()

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fake_namedtempfile)

    result = download_from_github(
        source_url="https://github.com/user/repo",
        artifact_id="123",
        artifact_type="code",
    )

    assert result.endswith(".tar.gz")
    assert Path(result).exists()


def test_download_from_github_with_git_suffix(monkeypatch, tmp_path):
    """Test GitHub download with .git suffix URL."""

    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            return [b"fake", b"content"]

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: FakeResponse())

    def fake_namedtempfile(**kwargs):
        tar_path = tmp_path / "fake.tar.gz"
        tar_path.touch()
        return type("TempFile", (), {"name": str(tar_path)})()

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fake_namedtempfile)

    result = download_from_github(
        source_url="https://github.com/user/project.git",
        artifact_id="123",
        artifact_type="code",
    )

    assert result.endswith(".tar.gz")
    assert Path(result).exists()


def test_download_from_github_wrong_type():
    with pytest.raises(FileDownloadError):
        download_from_github(
            source_url="https://github.com/user/repo",
            artifact_id="123",
            artifact_type="model",  # Should only accept "code"
        )


def test_download_from_github_parse_failure():
    with pytest.raises(FileDownloadError):
        download_from_github(
            source_url="https://example.com/not/github",  # Invalid URL
            artifact_id="123",
            artifact_type="code",
        )


def test_download_from_github_api_failure(monkeypatch):
    """Test GitHub API request failure."""

    class BadResponse:
        def raise_for_status(self):
            raise requests.RequestException("API failed")

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: BadResponse())

    with pytest.raises(FileDownloadError) as exc:
        download_from_github(
            source_url="https://github.com/user/repo",
            artifact_id="123",
            artifact_type="code",
        )

    assert "Failed to download from GitHub API" in str(exc.value)


def test_download_from_github_network_timeout(monkeypatch):
    """Test network timeout during download."""

    def timeout_get(url, **kwargs):
        import requests
        raise requests.Timeout("Request timed out")

    monkeypatch.setattr(requests, "get", timeout_get)

    with pytest.raises(FileDownloadError):
        download_from_github(
            source_url="https://github.com/user/repo",
            artifact_id="123",
            artifact_type="code",
        )


# =============================================================================
# fetch_github_code_metadata
# =============================================================================
def test_fetch_github_code_metadata_success(monkeypatch):
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


def test_fetch_github_code_metadata_with_git_suffix(monkeypatch):
    """Test metadata fetch with .git suffix URL."""
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "name": "project",
                "description": "desc",
                "language": "Python",
                "size": 1,
                "license": {"spdx_id": "MIT"},
                "stargazers_count": 5,
                "forks_count": 1,
                "open_issues_count": 0,
                "default_branch": "main",
                "clone_url": "https://github.com/user/project.git",
            }

    monkeypatch.setattr("requests.get", lambda url, timeout=10: FakeResponse())

    metadata = fetch_github_code_metadata("https://github.com/user/project.git")
    assert metadata["name"] == "project"
    assert metadata["metadata"]["stars"] == 5


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
