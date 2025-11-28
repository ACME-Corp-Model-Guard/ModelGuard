import os
import subprocess
import tarfile
from pathlib import Path

import pytest
import requests

from src.storage.downloaders.github import (
    FileDownloadError,
    _cleanup_temp_dir,
    _clone_repo,
    _make_tarball,
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


# =============================================================================
# _clone_repo
# =============================================================================
def test_clone_repo_success(monkeypatch, tmp_path):
    """Simulate successful git clone by mocking subprocess.run()."""

    class FakeCompleted:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())

    _clone_repo("https://github.com/user/repo.git", tmp_path.as_posix())


def test_clone_repo_failure(monkeypatch, tmp_path):
    """Simulate failing git clone."""

    class FakeCompleted:
        returncode = 1
        stderr = "fatal: repository not found"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())

    with pytest.raises(FileDownloadError):
        _clone_repo("https://github.com/bad/repo.git", tmp_path.as_posix())


# =============================================================================
# _make_tarball
# =============================================================================
def test_make_tarball(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    # Create some fake files
    (repo_path / "file1.txt").write_text("hello")
    subdir = repo_path / "sub"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("world")

    tar_path = _make_tarball(repo_path.as_posix(), "repo")

    assert os.path.exists(tar_path)

    with tarfile.open(tar_path, "r:gz") as tar:
        names = tar.getnames()
        assert "repo/file1.txt" in names
        assert "repo/sub/file2.txt" in names


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
    """Full pipeline using mocks."""
    monkeypatch.setattr(
        "src.storage.downloaders.github._parse_github_url",
        lambda url: ("user", "repo"),
    )

    def fake_clone(clone_url: str, dest: str):
        os.makedirs(dest, exist_ok=True)
        Path(dest, "a.txt").write_text("abc")

    monkeypatch.setattr("src.storage.downloaders.github._clone_repo", fake_clone)

    def fake_make_tar(repo_path: str, repo_name: str):
        tar_path = tmp_path / "fake.tar.gz"
        tar_path.write_text("TAR")
        return tar_path.as_posix()

    monkeypatch.setattr("src.storage.downloaders.github._make_tarball", fake_make_tar)

    monkeypatch.setattr(
        "src.storage.downloaders.github._cleanup_temp_dir",
        lambda d: None,
    )

    result = download_from_github(
        source_url="https://github.com/user/repo",
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


def test_download_from_github_clone_timeout(monkeypatch):
    def fake_clone(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=300)

    monkeypatch.setattr(
        "src.storage.downloaders.github._clone_repo",
        fake_clone,
    )

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


def test_fetch_github_code_metadata_invalid_url():
    with pytest.raises(ValueError):
        fetch_github_code_metadata("https://example.com/notgithub")


def test_fetch_github_code_metadata_http_error(monkeypatch):
    class FakeBadResponse:
        def raise_for_status(self):
            raise requests.RequestException("oops")

    monkeypatch.setattr("requests.get", lambda url, timeout=10: FakeBadResponse())

    with pytest.raises(Exception):
        fetch_github_code_metadata("https://github.com/user/repo")
