import os
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest
import requests
from unittest.mock import patch

from src.storage.downloaders.huggingface import (
    FileDownloadError,
    download_from_huggingface,
    fetch_huggingface_dataset_metadata,
    fetch_huggingface_model_metadata,
)


# =====================================================================================
# download_from_huggingface
# =====================================================================================
def test_hf_rejects_code_artifacts():
    """HuggingFace downloader must reject code artifacts."""
    with pytest.raises(FileDownloadError):
        download_from_huggingface(
            source_url="https://huggingface.co/owner/model",
            artifact_id="123",
            artifact_type="code",  # Literal type
        )


def test_hf_invalid_url_format():
    """Should fail if the URL does not contain huggingface.co/."""
    with pytest.raises(FileDownloadError):
        download_from_huggingface(
            source_url="https://example.com/not/hf",
            artifact_id="123",
            artifact_type="model",
        )


@patch("src.storage.downloaders.huggingface.huggingface_hub.get_secret_value")
def test_hf_url_parsing_with_datasets_prefix(mock_get_secret_value, monkeypatch, tmp_path):
    """
    Test that dataset URLs with 'datasets/' prefix are parsed correctly.
    This verifies the fix for the dataset URL parsing bug where URLs like
    https://huggingface.co/datasets/bookcorpus/bookcorpus were incorrectly
    parsed as repo_id='datasets/bookcorpus' instead of 'bookcorpus/bookcorpus'.
    """
    captured_repo_id = None

    mock_get_secret_value.return_value = "FAKE_TOKEN"

    def fake_snapshot_download(repo_id: str, repo_type: str, cache_dir: str, **kwargs):
        nonlocal captured_repo_id
        captured_repo_id = repo_id
        snapshot_path = os.path.join(cache_dir, "snapshot")
        os.makedirs(snapshot_path, exist_ok=True)
        Path(snapshot_path, "config.json").write_text("{}")
        return snapshot_path

    class FakeErrors:
        class RepositoryNotFoundError(Exception):
            pass

        class RevisionNotFoundError(Exception):
            pass

    # Mock huggingface_hub
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type(
            "FakeHFHub",
            (),
            {"snapshot_download": fake_snapshot_download, "errors": FakeErrors},
        ),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", FakeErrors)

    # Mock tempfile
    def fake_mkdtemp(prefix="", dir=None):
        path = tmp_path / "hf_tmp"
        path.mkdir(exist_ok=True)
        return path.as_posix()

    monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)

    def fake_namedtempfile(**kwargs):
        file_path = tmp_path / "artifact.tar.gz"
        file_path.write_text("FAKE TAR")
        return type("Tmp", (), {"name": file_path.as_posix()})()

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", lambda **k: fake_namedtempfile())

    # Mock tarfile
    class FakeTar:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def add(self, *a, **k):
            pass

    monkeypatch.setattr(tarfile, "open", lambda *a, **k: FakeTar())

    # Test various URL formats
    test_cases = [
        # (input_url, expected_repo_id)
        (
            "https://huggingface.co/datasets/bookcorpus/bookcorpus",
            "bookcorpus/bookcorpus",
        ),
        ("https://huggingface.co/datasets/rajpurkar/squad", "rajpurkar/squad"),
        ("https://huggingface.co/datasets/lerobot/pusht", "lerobot/pusht"),
        ("https://huggingface.co/datasets/ILSVRC/imagenet-1k", "ILSVRC/imagenet-1k"),
        (
            "https://huggingface.co/datasets/HuggingFaceM4/FairFace",
            "HuggingFaceM4/FairFace",
        ),
        (
            "https://huggingface.co/bert-base-uncased/bert-base-uncased",
            "bert-base-uncased/bert-base-uncased",
        ),
        ("https://huggingface.co/models/facebook/bart-large", "facebook/bart-large"),
        # Models without organization prefix (no "models/" and no org/)
        (
            "https://huggingface.co/distilbert-base-uncased-distilled-squad",
            "distilbert-base-uncased-distilled-squad",
        ),
        ("https://huggingface.co/bert-base-uncased", "bert-base-uncased"),
    ]

    for url, expected_repo_id in test_cases:
        captured_repo_id = None
        artifact_type = "dataset" if "/datasets/" in url else "model"

        download_from_huggingface(
            source_url=url, artifact_id="test123", artifact_type=artifact_type
        )

        assert (
            captured_repo_id == expected_repo_id
        ), f"URL {url} parsed to {captured_repo_id}, expected {expected_repo_id}"


@patch("src.storage.downloaders.huggingface.huggingface_hub.get_secret_value")
def test_download_from_huggingface_success(mock_get_secret_value, monkeypatch, tmp_path):
    """
    Full pipeline:
    - mock snapshot_download
    - mock tarfile creation
    - mock cleanup
    """

    mock_get_secret_value.return_value = "FAKE_TOKEN"

    # ------------------------------------------------------------------
    # Mock snapshot_download
    # ------------------------------------------------------------------

    def fake_snapshot_download(repo_id: str, repo_type: str, cache_dir: str, **kwargs):
        # snapshot path (directory with files)
        snapshot_path = os.path.join(cache_dir, "snapshot")
        os.makedirs(snapshot_path, exist_ok=True)
        Path(snapshot_path, "config.json").write_text("{}")
        return snapshot_path

    # Fake huggingface_hub module
    class FakeErrors:
        class RepositoryNotFoundError(Exception):
            pass

        class RevisionNotFoundError(Exception):
            pass

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type(
            "FakeHFHub",
            (),
            {"snapshot_download": fake_snapshot_download, "errors": FakeErrors},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub.errors",
        FakeErrors,
    )

    # ------------------------------------------------------------------
    # Mock tarfile.open so we don’t create a real tarball
    # ------------------------------------------------------------------
    class FakeTar:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def add(self, *a, **k):
            pass

    monkeypatch.setattr(tarfile, "open", lambda *a, **k: FakeTar())

    # ------------------------------------------------------------------
    # Mock tempfile so we control created paths
    # ------------------------------------------------------------------
    def fake_mkdtemp(prefix="", dir=None):
        path = tmp_path / "hf_tmp"
        path.mkdir(exist_ok=True)
        return path.as_posix()

    monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)

    # Output tar file path
    def fake_namedtempfile(**kwargs):
        file_path = tmp_path / "artifact.tar.gz"
        file_path.write_text("FAKE TAR")
        return type("Tmp", (), {"name": file_path.as_posix()})()

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", lambda **k: fake_namedtempfile())

    # ------------------------------------------------------------------
    # Run downloader
    # ------------------------------------------------------------------
    result_path = download_from_huggingface(
        source_url="https://huggingface.co/owner/model",
        artifact_id="abc",
        artifact_type="model",
    )

    assert result_path.endswith(".tar.gz")
    assert Path(result_path).exists()


def test_download_from_huggingface_missing_repo(monkeypatch):
    """
    Test RepositoryNotFoundError mapping to FileDownloadError.
    """

    class FakeErrors:
        class RepositoryNotFoundError(Exception):
            pass

        class RevisionNotFoundError(Exception):
            pass

    def fake_snapshot_download(*a, **k):
        raise FakeErrors.RepositoryNotFoundError("Not found")

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type(
            "FakeHFHub",
            (),
            {"snapshot_download": fake_snapshot_download, "errors": FakeErrors},
        ),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", FakeErrors)

    with pytest.raises(FileDownloadError):
        download_from_huggingface(
            source_url="https://huggingface.co/owner/model",
            artifact_id="xyz",
            artifact_type="model",
        )


def test_download_from_huggingface_general_failure(monkeypatch):
    """
    Any other unexpected error should be wrapped in FileDownloadError.
    """

    class FakeErrors:
        class RepositoryNotFoundError(Exception):
            pass

        class RevisionNotFoundError(Exception):
            pass

    def fake_snapshot_download(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type(
            "FakeHFHub",
            (),
            {"snapshot_download": fake_snapshot_download, "errors": FakeErrors},
        ),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", FakeErrors)

    with pytest.raises(FileDownloadError) as exc:
        download_from_huggingface(
            source_url="https://huggingface.co/owner/repo",
            artifact_id="id",
            artifact_type="model",
        )

    assert "HuggingFace download failed" in str(exc.value)


# =====================================================================================
# Metadata Fetchers
# =====================================================================================
def test_fetch_hf_model_metadata_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "safetensors": {"total": 123},
                "cardData": {"license": "MIT"},
                "downloads": 10,
                "likes": 2,
            }

    monkeypatch.setattr(requests, "get", lambda url, timeout=10: FakeResponse())

    metadata = fetch_huggingface_model_metadata("https://huggingface.co/owner/model")
    assert metadata["name"] == "model"
    assert metadata["size"] == 123
    assert metadata["license"] == "MIT"
    assert metadata["metadata"]["downloads"] == 10


def test_fetch_hf_model_metadata_invalid_url():
    with pytest.raises(ValueError):
        fetch_huggingface_model_metadata("https://example.com/not/hf")


def test_fetch_hf_model_metadata_http_error(monkeypatch):
    class BadResponse:
        def raise_for_status(self):
            raise requests.RequestException("bad")

    monkeypatch.setattr(requests, "get", lambda url, timeout=10: BadResponse())

    with pytest.raises(Exception):
        fetch_huggingface_model_metadata("https://huggingface.co/owner/model")


def test_fetch_hf_dataset_metadata_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "downloads": 42,
                "likes": 7,
                "cardData": {"description": "test"},
            }

    monkeypatch.setattr(requests, "get", lambda url, timeout=10: FakeResponse())

    metadata = fetch_huggingface_dataset_metadata("https://huggingface.co/datasets/owner/dataset")

    assert metadata["name"] == "dataset"
    assert metadata["metadata"]["downloads"] == 42
    assert metadata["metadata"]["likes"] == 7


def test_fetch_hf_dataset_metadata_invalid_url():
    with pytest.raises(ValueError):
        fetch_huggingface_dataset_metadata("https://huggingface.co/owner/model")


def test_fetch_hf_dataset_metadata_http_error(monkeypatch):
    class BadResponse:
        def raise_for_status(self):
            raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "get", lambda url, timeout=10: BadResponse())

    with pytest.raises(Exception):
        fetch_huggingface_dataset_metadata("https://huggingface.co/datasets/owner/dataset")
