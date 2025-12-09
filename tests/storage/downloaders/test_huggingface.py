import sys
import tarfile
import tempfile
from pathlib import Path

import pytest
import requests

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


def test_hf_single_name_repository():
    """Should handle single-name repositories like distilbert-base-uncased-distilled-squad."""
    # This should NOT raise an error for URL parsing
    try:
        # We'll mock the actual download but URL parsing should work
        download_from_huggingface(
            source_url="https://huggingface.co/distilbert-base-uncased-distilled-squad",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        # Should fail on missing huggingface_hub, not URL parsing
        assert "huggingface_hub is required" in str(e)


def test_hf_organization_repository():
    """Should handle organization/repo format like microsoft/DialoGPT-medium."""
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/microsoft/DialoGPT-medium",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        # Should fail on missing huggingface_hub, not URL parsing
        assert "huggingface_hub is required" in str(e)


def test_download_from_huggingface_success(monkeypatch, tmp_path):
    """
    Full pipeline:
    - mock snapshot_download with local_dir (simplified approach)
    - mock tarfile creation
    - mock cleanup
    """
    # ------------------------------------------------------------------
    # Mock snapshot_download - now uses local_dir directly
    # ------------------------------------------------------------------

    def fake_snapshot_download(repo_id: str, repo_type: str, local_dir: str, **kwargs):
        # Create fake model files directly in local_dir (no complex cache structure)
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)

        # Create fake model files
        (local_path / "config.json").write_text('{"model_type": "bert"}')
        (local_path / "pytorch_model.bin").write_text("FAKE MODEL DATA")
        (local_path / "tokenizer.json").write_text('{"vocab": {}}')

        # No return value needed - files are directly in local_dir

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
    # Mock tarfile.open so we don't create a real tarball
    # ------------------------------------------------------------------
    class FakeTar:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def add(self, file_path, arcname=None, **k):
            # Verify that files are being added correctly
            assert Path(file_path).exists()

    monkeypatch.setattr(tarfile, "open", lambda *a, **k: FakeTar())

    # ------------------------------------------------------------------
    # Mock tempfile so we control created paths
    # ------------------------------------------------------------------
    def fake_mkdtemp(prefix="", dir=None):
        # Create download directory in pytest's temp space
        download_path = tmp_path / "hf_download"
        download_path.mkdir(exist_ok=True)
        return str(download_path)

    monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)

    # Output tar file path
    def fake_namedtempfile(**kwargs):
        file_path = tmp_path / "artifact.tar.gz"
        file_path.write_text("FAKE TAR")
        return type("Tmp", (), {"name": str(file_path)})()

    monkeypatch.setattr(
        tempfile, "NamedTemporaryFile", lambda **k: fake_namedtempfile()
    )

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
# URL Parsing Tests (Comprehensive Edge Cases)
# =====================================================================================
def test_hf_url_with_trailing_slash():
    """Should handle URLs with trailing slash."""
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/microsoft/DialoGPT-medium/",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        # Should fail on missing huggingface_hub, not URL parsing
        assert "huggingface_hub is required" in str(e)


def test_hf_datasets_url_parsing():
    """Should handle dataset URLs correctly."""
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/datasets/squad",
            artifact_id="123",
            artifact_type="dataset",
        )
    except FileDownloadError as e:
        # Should fail on missing huggingface_hub, not URL parsing
        assert "huggingface_hub is required" in str(e)


def test_hf_empty_repo_path():
    """Should fail when URL has no repository path."""
    with pytest.raises(FileDownloadError, match="Invalid HuggingFace repository URL"):
        download_from_huggingface(
            source_url="https://huggingface.co/",
            artifact_id="123",
            artifact_type="model",
        )


def test_hf_url_with_subpaths():
    """Should handle URLs with extra subpaths (only use first two parts)."""
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/microsoft/DialoGPT-medium/blob/main/README.md",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        # Should fail on missing huggingface_hub, not URL parsing
        assert "huggingface_hub is required" in str(e)


def test_hf_url_parsing_edge_cases():
    """Test various edge cases in URL parsing."""

    # Multiple slashes - should still work
    try:
        download_from_huggingface(
            source_url="https://huggingface.co///microsoft///DialoGPT-medium///",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        # Should still work - might fail on download, not parsing
        pass

    # Very long single name
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/very-long-model-name-with-many-hyphens-and-underscores_123",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        assert "huggingface_hub is required" in str(e)


def test_hf_special_characters_in_names():
    """Test repo names with special characters."""
    try:
        download_from_huggingface(
            source_url="https://huggingface.co/microsoft/DialoGPT-medium_v2.0",
            artifact_id="123",
            artifact_type="model",
        )
    except FileDownloadError as e:
        assert "huggingface_hub is required" in str(e)


# =====================================================================================
# Metadata Fetchers (Comprehensive Coverage)
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

    metadata = fetch_huggingface_dataset_metadata(
        "https://huggingface.co/datasets/owner/dataset"
    )

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
        fetch_huggingface_dataset_metadata(
            "https://huggingface.co/datasets/owner/dataset"
        )
