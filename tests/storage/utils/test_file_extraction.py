import tarfile
from pathlib import Path

import src.storage.file_extraction as fx


# ---------------------------------------------------------------------
# Helper to create a tar.gz file with named entries + contents
# ---------------------------------------------------------------------
def create_tar(tmp_path: Path, files: dict[str, str]) -> str:
    tar_path = tmp_path / "test.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name, content in files.items():
            file_path = tmp_path / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

            tar.add(file_path, arcname=name)

    return str(tar_path)


# ============================================================
# extract_files_from_tar()
# ============================================================


def test_extract_files_from_tar_basic(tmp_path):
    tar_path = create_tar(
        tmp_path,
        {
            "a.py": "print('hello')",
            "b.txt": "some text",
        },
    )

    result = fx.extract_files_from_tar(tar_path)

    assert result["a.py"] == "print('hello')"
    assert result["b.txt"] == "some text"
    assert len(result) == 2


def test_extract_files_from_tar_truncation(tmp_path):
    long_text = "x" * 10000
    tar_path = create_tar(tmp_path, {"big.txt": long_text})

    result = fx.extract_files_from_tar(tar_path, max_chars=100)

    assert len(result["big.txt"]) == 100


def test_extract_files_from_tar_handles_bad_file(tmp_path, monkeypatch):
    """
    Simulate tar.extractfile() returning None for a member.
    """
    tar_path = create_tar(tmp_path, {"good.txt": "ok"})

    # Patch extractfile() to fail for the first call
    orig_open = tarfile.TarFile.extractfile

    def fake_extractfile(self, m):
        if m.name == "good.txt":
            return None  # simulate failure
        return orig_open(self, m)

    monkeypatch.setattr(tarfile.TarFile, "extractfile", fake_extractfile)

    result = fx.extract_files_from_tar(tar_path)
    # Should return empty because extraction failed
    assert result == {}


def test_extract_files_from_tar_invalid_tar(monkeypatch):
    monkeypatch.setattr(
        tarfile,
        "open",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("boom")),
    )

    result = fx.extract_files_from_tar("not_a_tar.gz")
    assert result == {}  # graceful fail


# ============================================================
# select_relevant_files()
# ============================================================


def test_select_relevant_files_regular_extensions():
    files = {
        "a.py": "aaa",
        "b.txt": "bbb",
        "c.md": "ccc",
        "image.png": "binary-ish",
    }

    selected = fx.select_relevant_files(
        files,
        include_ext=[".py", ".txt", ".md"],
        max_files=10,
        prioritize_readme=True,
    )

    assert set(selected.keys()) == {"a.py", "b.txt", "c.md"}


def test_select_relevant_files_prioritize_readme():
    files = {
        "b.py": "bbb",
        "README.md": "important",
        "a.txt": "aaa",
    }

    selected = fx.select_relevant_files(
        files,
        include_ext=[".py", ".txt"],
        max_files=3,
        prioritize_readme=True,
    )

    keys = list(selected.keys())
    assert keys[0].lower().startswith("readme")  # README goes first


def test_select_relevant_files_no_readme_priority():
    files = {
        "b.py": "bbb",
        "README.md": "important",
        "a.txt": "aaa",
    }

    selected = fx.select_relevant_files(
        files,
        include_ext=[".py", ".txt"],
        max_files=3,
        prioritize_readme=False,
    )

    assert list(selected.keys())[0] == "a.txt"  # alphabetical only


def test_select_relevant_files_max_files_limit():
    files = {f"file{i}.py": "x" for i in range(10)}

    selected = fx.select_relevant_files(
        files,
        include_ext=[".py"],
        max_files=3,
        prioritize_readme=True,
    )

    assert len(selected) == 3


def test_select_relevant_files_ext_case_insensitive():
    files = {
        "A.PY": "x",
        "b.TxT": "y",
        "ignore.bin": "z",
    }

    selected = fx.select_relevant_files(
        files,
        include_ext=[".py", ".txt"],
        max_files=10,
    )

    assert set(selected.keys()) == {"A.PY", "b.TxT"}


# ============================================================
# extract_relevant_files() high-level
# ============================================================


def test_extract_relevant_files_integration(tmp_path):
    """
    Creates a real tar.gz, extracts it, then filters.
    """
    tar_path = create_tar(
        tmp_path,
        {
            "a.py": "print('a')",
            "b.txt": "hello",
            "README.md": "readme content",
            "image.png": "binary-ish",
        },
    )

    result = fx.extract_relevant_files(
        tar_path,
        include_ext=[".py", ".txt"],
        max_files=2,
        max_chars=100,
        prioritize_readme=True,
    )

    # README.md should appear first, even though ".md" not in include_ext
    # because prioritize_readme=True
    keys = list(result.keys())

    assert keys[0].lower().startswith("readme")
    assert len(result) == 2  # max_files enforced
