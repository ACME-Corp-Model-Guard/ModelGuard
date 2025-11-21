import pytest

from src.storage.downloaders.dispatchers import (
    FileDownloadError,
    download_artifact,
    fetch_artifact_metadata,
)
from src.storage.downloaders.github import FileDownloadError as GitHubError
from src.storage.downloaders.huggingface import FileDownloadError as HFError


# ============================================================
# download_artifact tests
# ============================================================
def test_dispatch_to_huggingface(monkeypatch):
    """Correctly dispatches HF URLs to download_from_huggingface()."""

    def fake_hf(url, artifact_id, artifact_type):
        assert url == "https://huggingface.co/owner/repo"
        assert artifact_id == "123"
        assert artifact_type == "model"
        return "/tmp/hf.tar.gz"

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.download_from_huggingface",
        fake_hf,
    )

    result = download_artifact(
        source_url="https://huggingface.co/owner/repo",
        artifact_id="123",
        artifact_type="model",
    )

    assert result == "/tmp/hf.tar.gz"


def test_dispatch_to_github(monkeypatch):
    """Correctly dispatches GitHub URLs to download_from_github()."""

    def fake_git(url, artifact_id, artifact_type):
        assert url == "https://github.com/user/repo"
        assert artifact_id == "999"
        assert artifact_type == "code"
        return "/tmp/git.tar.gz"

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.download_from_github",
        fake_git,
    )

    result = download_artifact(
        source_url="https://github.com/user/repo",
        artifact_id="999",
        artifact_type="code",
    )

    assert result == "/tmp/git.tar.gz"


def test_dispatcher_hf_error(monkeypatch):
    """HF errors should be wrapped into dispatcher-level FileDownloadError."""

    def fake_hf(*a, **k):
        raise HFError("HF failed")

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.download_from_huggingface",
        fake_hf,
    )

    with pytest.raises(FileDownloadError) as exc:
        download_artifact("https://huggingface.co/x/y", "321", "model")

    assert "HF failed" in str(exc.value)


def test_dispatcher_github_error(monkeypatch):
    """GitHub errors should be wrapped into dispatcher-level FileDownloadError."""

    def fake_git(*a, **k):
        raise GitHubError("GitHub failed")

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.download_from_github",
        fake_git,
    )

    with pytest.raises(FileDownloadError) as exc:
        download_artifact("https://github.com/user/repo", "321", "code")

    assert "GitHub failed" in str(exc.value)


def test_dispatcher_invalid_url():
    """Unsupported URLs should raise FileDownloadError."""

    with pytest.raises(FileDownloadError):
        download_artifact("https://example.com/not-supported", "123", "model")


# ============================================================
# fetch_artifact_metadata tests
# ============================================================
def test_fetch_model_metadata(monkeypatch):
    """Correct metadata fetcher selected for HF model URLs."""

    def fake_model(url):
        assert url == "https://huggingface.co/owner/model"
        return {"fake": "model-metadata"}

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.fetch_huggingface_model_metadata",
        fake_model,
    )

    result = fetch_artifact_metadata(
        url="https://huggingface.co/owner/model",
        artifact_type="model",
    )

    assert result == {"fake": "model-metadata"}


def test_fetch_dataset_metadata(monkeypatch):
    """Correct metadata fetcher selected for HF dataset URLs."""

    def fake_dataset(url):
        assert url == "https://huggingface.co/datasets/mydata"
        return {"fake": "dataset-metadata"}

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.fetch_huggingface_dataset_metadata",
        fake_dataset,
    )

    result = fetch_artifact_metadata(
        url="https://huggingface.co/datasets/mydata",
        artifact_type="dataset",
    )

    assert result == {"fake": "dataset-metadata"}


def test_fetch_code_metadata(monkeypatch):
    """Correct metadata fetcher selected for GitHub URLs."""

    def fake_code(url):
        assert url == "https://github.com/user/repo"
        return {"fake": "code-metadata"}

    monkeypatch.setattr(
        "src.storage.downloaders.dispatchers.fetch_github_code_metadata",
        fake_code,
    )

    result = fetch_artifact_metadata(
        url="https://github.com/user/repo",
        artifact_type="code",
    )

    assert result == {"fake": "code-metadata"}


def test_fetch_metadata_invalid_model_url():
    """Non-HF model URL should raise ValueError."""
    with pytest.raises(ValueError):
        fetch_artifact_metadata("https://example.com/not-hf", "model")


def test_fetch_metadata_invalid_dataset_url():
    """Non-HF dataset URL should raise ValueError."""
    with pytest.raises(ValueError):
        fetch_artifact_metadata("https://example.com/not-hf", "dataset")


def test_fetch_metadata_invalid_code_url():
    """Non-GitHub code URL should raise ValueError."""
    with pytest.raises(ValueError):
        fetch_artifact_metadata("https://example.com/not-github", "code")


def test_fetch_metadata_invalid_artifact_type():
    """Unknown artifact types should raise ValueError."""
    with pytest.raises(ValueError):
        fetch_artifact_metadata("https://huggingface.co/x/y", "unknown-type")
