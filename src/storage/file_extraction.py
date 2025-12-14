"""
Utilities for extracting relevant files from .tar.gz archives.

Used by LLM-driven metrics to extract representative samples of an
artifact's code, documentation, or dataset contents.
"""

from __future__ import annotations

import re
import tarfile
from typing import Dict, Iterable, List, Tuple

from src.logutil import clogger


# ====================================================================================
# TAR EXTRACTION (LOW-LEVEL)
# ====================================================================================
# Reads files from a .tar.gz archive and returns a mapping:
#     { "path/to/file.ext": "file contents" }
#
# Does NOT apply filtering or prioritization. That is handled by
# select_relevant_files() below.
# ------------------------------------------------------------------------------------


def extract_files_from_tar(
    tar_path: str,
    max_chars: int = 4000,
) -> Dict[str, str]:
    """
    Extract all text-like files from the tar archive, truncated to max_chars.
    """
    files: Dict[str, str] = {}

    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]

            for m in members:
                try:
                    f = tar.extractfile(m)
                    if not f:
                        continue

                    # Defensive decoding — ignore binary garbage
                    text = f.read().decode("utf-8", errors="ignore")
                    files[m.name] = text[:max_chars]

                except Exception as e:
                    clogger.warning(f"[file_extraction] Failed to extract {m.name}: {e}")

    except Exception as e:
        clogger.error(f"[file_extraction] Failed to open tar: {e}")

    return files


# ====================================================================================
# CONTENT FILTERING
# ====================================================================================
# Remove junk patterns from file content that waste LLM token budget.
# ------------------------------------------------------------------------------------

# Patterns to exclude from file content (case-insensitive)
JUNK_LINE_PATTERNS = [
    r"^\[unused\d+\]$",  # [unused0], [unused123], etc.
    r"^unused\d+$",  # unused0, unused123, etc.
]


def filter_junk_lines(content: str) -> str:
    """
    Remove lines matching junk patterns that waste token budget.

    Filters out enumeration patterns like:
    - [unused0], [unused1], ..., [unused999]
    - Other repetitive non-informative patterns

    Args:
        content: Raw file content

    Returns:
        Filtered content with junk lines removed
    """
    if not content:
        return content

    lines = content.splitlines()

    # Compile patterns once
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in JUNK_LINE_PATTERNS]

    # Filter out matching lines
    filtered_lines = [
        line
        for line in lines
        if not any(pattern.match(line.strip()) for pattern in compiled_patterns)
    ]

    return "\n".join(filtered_lines)


# ====================================================================================
# FILE PRIORITIZATION / SELECTION
# ====================================================================================
# Given a dictionary of extracted {path -> contents}, select only the "best"
# files for analysis based on extension preference and ordering rules.
# ------------------------------------------------------------------------------------

# Files to exclude entirely (waste token budget, provide no useful metadata)
EXCLUDE_FILENAMES = {
    "vocab.txt",
    "vocab.json",
    "tokenizer.json",
    "merges.txt",
    "added_tokens.json",
    "special_tokens_map.json",
}


def select_relevant_files(
    all_files: Dict[str, str],
    include_ext: Iterable[str],
    max_files: int = 5,
    prioritize_readme: bool = True,
) -> Dict[str, str]:
    """
    Filter and select the most relevant files.

    Args:
        all_files: Mapping of filename -> text contents.
        include_ext: Iterable of file extensions to include (e.g. {".py", ".txt"}).
        max_files: Maximum number of files to return.
        prioritize_readme: Whether to rank README-like files highest.

    Returns:
        Dictionary {filename: content} for selected files.
    """

    def is_readme(name: str) -> bool:
        n = name.lower()
        return "readme" in n or n.endswith("readme.md") or n.endswith("readme")

    def is_excluded(name: str) -> bool:
        """Check if filename should be excluded entirely."""
        basename = name.split("/")[-1].lower()  # Get just the filename
        return basename in EXCLUDE_FILENAMES

    # Filter by extension OR README special-case, excluding vocab/tokenizer files
    candidates: List[Tuple[str, str]] = []
    for name, content in all_files.items():
        lower = name.lower()

        # Skip excluded files entirely
        if is_excluded(name):
            clogger.debug(f"[file_extraction] Excluding {name} (vocab/tokenizer file)")
            continue

        if prioritize_readme and is_readme(lower):
            # Filter junk lines from README content
            filtered_content = filter_junk_lines(content)
            candidates.append((name, filtered_content))
            continue

        if any(lower.endswith(ext) for ext in include_ext):
            # Filter junk lines from all content
            filtered_content = filter_junk_lines(content)
            candidates.append((name, filtered_content))

    # Sort README first (if enabled), then alphabetically
    candidates.sort(
        key=lambda pair: (
            0 if (prioritize_readme and is_readme(pair[0])) else 1,
            pair[0].lower(),
        )
    )

    # Limit number of files
    selected = dict(candidates[:max_files])

    return selected


# ====================================================================================
# HIGH-LEVEL ENTRY POINT
# ====================================================================================
# This is the method most metrics will call directly.
#
# Example:
#     files = extract_relevant_files("/tmp/repo.tar.gz", [".py", ".txt"])
#
# ------------------------------------------------------------------------------------


def extract_relevant_files(
    tar_path: str,
    include_ext: Iterable[str],
    max_files: int = 5,
    max_chars: int = 4000,
    prioritize_readme: bool = True,
) -> Dict[str, str]:
    """
    High-level helper to extract and select relevant files from a .tar.gz archive.

    Combines:
        - extract_files_from_tar()
        - select_relevant_files()

    Returns:
        Mapping of filename -> truncated text content.
    """
    all_files = extract_files_from_tar(tar_path, max_chars=max_chars)

    return select_relevant_files(
        all_files,
        include_ext=include_ext,
        max_files=max_files,
        prioritize_readme=prioritize_readme,
    )
