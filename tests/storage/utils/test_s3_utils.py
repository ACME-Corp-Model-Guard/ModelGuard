from unittest.mock import MagicMock

import pytest

import src.storage.s3_utils as s3_utils


# ---------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("ARTIFACTS_BUCKET", "test-bucket")
    # s3_utils imported ARTIFACTS_BUCKET at import time:
    s3_utils.ARTIFACTS_BUCKET = "test-bucket"


@pytest.fixture
def mock_s3(monkeypatch):
    """
    Patch get_s3() to return a mock S3 client.
    """
    mock_client = MagicMock()
    monkeypatch.setattr(s3_utils, "get_s3", lambda: mock_client)
    return mock_client


@pytest.fixture
def mock_download_artifact(monkeypatch, tmp_path):
    """
    Patch download_artifact() to return a temp file path.
    """
    temp_file = tmp_path / "artifact.tar.gz"
    temp_file.write_text("dummy")

    monkeypatch.setattr(
        s3_utils,
        "download_artifact",
        lambda source_url, artifact_id, artifact_type: str(temp_file),
    )
    return str(temp_file)


# ---------------------------------------------------------------------
# upload_file()
# ---------------------------------------------------------------------
def test_upload_file_success(mock_s3, tmp_path):
    local_file = tmp_path / "data.txt"
    local_file.write_text("hello")

    s3_utils.upload_file("path/key.txt", str(local_file))

    mock_s3.upload_file.assert_called_once_with(
        str(local_file),
        "test-bucket",
        "path/key.txt",
    )


def test_upload_file_client_error(mock_s3, tmp_path):
    from botocore.exceptions import ClientError

    mock_s3.upload_file.side_effect = ClientError(
        {"Error": {"Code": "Fail"}}, "UploadFile"
    )

    local_file = tmp_path / "data.txt"
    local_file.write_text("hello")

    with pytest.raises(ClientError):
        s3_utils.upload_file("path/key.txt", str(local_file))


# ---------------------------------------------------------------------
# download_file()
# ---------------------------------------------------------------------
def test_download_file_success(mock_s3, tmp_path):
    local_path = tmp_path / "dl.bin"

    s3_utils.download_file("path/key.bin", str(local_path))

    mock_s3.download_file.assert_called_once_with(
        "test-bucket",
        "path/key.bin",
        str(local_path),
    )


def test_download_file_client_error(mock_s3, tmp_path):
    from botocore.exceptions import ClientError

    mock_s3.download_file.side_effect = ClientError(
        {"Error": {"Code": "Fail"}}, "DownloadFile"
    )

    with pytest.raises(ClientError):
        s3_utils.download_file("path/key.bin", "/tmp/file")


# ---------------------------------------------------------------------
# generate_presigned_url()
# ---------------------------------------------------------------------
def test_generate_presigned_url(mock_s3):
    mock_s3.generate_presigned_url.return_value = "http://signed-url"

    result = s3_utils.generate_presigned_url("path/key.bin", expiration=1234)

    assert result == "http://signed-url"
    mock_s3.generate_presigned_url.assert_called_once()


# ---------------------------------------------------------------------
# upload_artifact_to_s3()
# ---------------------------------------------------------------------
def test_upload_artifact_to_s3_success(mock_s3, mock_download_artifact):
    s3_utils.upload_artifact_to_s3(
        artifact_id="A1",
        artifact_type="model",
        s3_key="models/A1.tar.gz",
        source_url="http://example.com",
    )

    # ensure upload_file was called
    mock_s3.upload_file.assert_called_once()


def test_upload_artifact_to_s3_missing_bucket(monkeypatch):
    monkeypatch.setattr(s3_utils, "ARTIFACTS_BUCKET", "")

    with pytest.raises(ValueError):
        s3_utils.upload_artifact_to_s3(
            "A1", "model", "models/A1.tar.gz", "http://example.com"
        )


def test_upload_artifact_to_s3_download_error(monkeypatch):
    from src.storage.downloaders.dispatchers import FileDownloadError

    monkeypatch.setattr(
        s3_utils,
        "download_artifact",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileDownloadError("boom")),
    )

    with pytest.raises(FileDownloadError):
        s3_utils.upload_artifact_to_s3(
            "A1", "model", "models/A1.tar.gz", "http://bad.example.com"
        )


# ---------------------------------------------------------------------
# download_artifact_from_s3()
# ---------------------------------------------------------------------
def test_download_artifact_from_s3_success(mock_s3):
    s3_utils.download_artifact_from_s3("A1", "models/A1.tar.gz", "/tmp/file")

    mock_s3.download_file.assert_called_once()


def test_download_artifact_from_s3_missing_bucket(monkeypatch):
    monkeypatch.setattr(s3_utils, "ARTIFACTS_BUCKET", "")
    with pytest.raises(ValueError):
        s3_utils.download_artifact_from_s3("A1", "models/A1.tar.gz", "/tmp/x")


# ---------------------------------------------------------------------
# generate_s3_download_url()
# ---------------------------------------------------------------------
def test_generate_s3_download_url(mock_s3):
    mock_s3.generate_presigned_url.return_value = "https://signed-url"

    result = s3_utils.generate_s3_download_url("A1", "models/A1.tar.gz", expiration=999)

    assert result == "https://signed-url"


# ---------------------------------------------------------------------
# clear_bucket()
# ---------------------------------------------------------------------
def test_clear_bucket(mock_s3):
    paginator = MagicMock()
    mock_s3.get_paginator.return_value = paginator

    paginator.paginate.return_value = [
        {"Contents": [{"Key": "a"}, {"Key": "b"}]},
        {"Contents": [{"Key": "c"}]},
    ]

    deleted = s3_utils.clear_bucket("test-bucket")
    assert deleted == 3

    assert mock_s3.delete_objects.call_count == 2


# ---------------------------------------------------------------------
# delete_prefix()
# ---------------------------------------------------------------------
def test_delete_prefix(mock_s3):
    paginator = MagicMock()
    mock_s3.get_paginator.return_value = paginator

    paginator.paginate.return_value = [
        {"Contents": [{"Key": "x/y/1"}, {"Key": "x/y/2"}]},
    ]

    deleted = s3_utils.delete_prefix("test-bucket", "x/y/")
    assert deleted == 2

    mock_s3.delete_objects.assert_called_once()


# ---------------------------------------------------------------------
# delete_objects()
# ---------------------------------------------------------------------
def test_delete_objects(mock_s3):
    deleted = s3_utils.delete_objects("test-bucket", ["a", "b", "c"])
    assert deleted == 3

    mock_s3.delete_objects.assert_called_once()


def test_delete_objects_empty(mock_s3):
    deleted = s3_utils.delete_objects("test-bucket", [])
    assert deleted == 0
    mock_s3.delete_objects.assert_not_called()
