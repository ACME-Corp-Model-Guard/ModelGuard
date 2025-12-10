import os
import tarfile
from pathlib import Path

import pytest
import requests

from src.storage.downloaders.github import (
    FileDownloadError,
    _cleanup_temp_dir,
    _download_repo_zip,
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
# _download_repo_zip
# =============================================================================
def test_download_repo_zip_success(monkeypatch, tmp_path):
    """Test successful repo download via GitHub REST API."""
    import zipfile
    import io

    # Create a fake zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("repo-main/README.md", "# Test Repo")
        zip_file.writestr("repo-main/src/code.py", "print('hello')")
    zip_buffer.seek(0)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            while True:
                chunk = zip_buffer.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())

    result_path = _download_repo_zip("user", "repo", tmp_path.as_posix())

    assert os.path.exists(result_path)
    assert "repo-main" in result_path
    assert os.path.exists(os.path.join(result_path, "README.md"))


def test_download_repo_zip_not_found(monkeypatch, tmp_path):
    """Test handling of 404 (repository not found)."""

    class FakeResponse:
        status_code = 404

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())

    with pytest.raises(FileDownloadError, match="not found"):
        _download_repo_zip("user", "nonexistent", tmp_path.as_posix())


def test_download_repo_zip_branch_fallback(monkeypatch, tmp_path):
    """Test that it falls back to master branch when main doesn't exist."""
    import zipfile
    import io

    call_count = {"count": 0}

    def fake_get(*args, **kwargs):
        call_count["count"] += 1
        url = args[0] if args else kwargs.get("url", "")

        # All calls with "main" in URL return 404
        if "main" in url:

            class NotFound:
                status_code = 404

            return NotFound()

        # Calls with "master" succeed
        if "master" in url:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                zip_file.writestr("repo-master/README.md", "# Test")
            zip_buffer.seek(0)

            class Success:
                status_code = 200

                def raise_for_status(self):
                    pass

                def iter_content(self, chunk_size=8192):
                    while True:
                        chunk = zip_buffer.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk

            return Success()

        # Shouldn't get here
        class NotFound:
            status_code = 404

        return NotFound()

    monkeypatch.setattr(requests, "get", fake_get)

    result = _download_repo_zip("user", "repo", tmp_path.as_posix())
    assert "repo-master" in result
    assert os.path.exists(result)
    assert call_count["count"] >= 2  # Should have tried main (1-2 times), then master


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

    def fake_download_zip(owner: str, repo: str, dest_dir: str, branch: str = "main"):
        # Create a fake extracted directory
        extracted_dir = os.path.join(dest_dir, f"{repo}-main")
        os.makedirs(extracted_dir, exist_ok=True)
        Path(extracted_dir, "a.txt").write_text("abc")
        return extracted_dir

    monkeypatch.setattr(
        "src.storage.downloaders.github._download_repo_zip", fake_download_zip
    )

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
