from __future__ import annotations

import logging
import os
from logging import handlers

_SILENT_SENTINEL = 100


def _parse_level(raw: str | None) -> int | None:
    if raw is None:
        return None
    v = raw.strip().lower()
    if v in {"0", "off", "none", "silent"}:
        return _SILENT_SENTINEL
    if v == "1":
        return logging.INFO
    if v == "2":
        return logging.DEBUG
    return getattr(logging, v.upper(), logging.INFO)


def setup_logging() -> None:
    lvl = _parse_level(os.getenv("LOG_LEVEL"))
    log_path = os.getenv("LOG_FILE", "app.log")

    if lvl == _SILENT_SENTINEL:
        try:
            # create blank file and do not attach handlers
            with open(log_path, "w", encoding="utf-8"):
                pass
        except Exception:
            # even if path is bad, never crash
            pass
        return

    # normal logging
    logger = logging.getLogger()
    logger.setLevel(lvl or logging.INFO)
    logger.handlers[:] = []

    try:
        fh = handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=1, encoding="utf-8"
        )
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Test the file by writing a simple message to verify it's working
        if lvl == logging.INFO:
            logger.info("Log initialized with INFO level")
        elif lvl == logging.DEBUG:
            logger.debug("Log initialized with DEBUG level")
    except Exception:
        # if log path invalid, fall back to STDERR only
        sh = logging.StreamHandler()
        fmt = logging.Formatter("%(levelname)s: %(message)s")
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        # Log a message to indicate the log file path was invalid
        logger.error(f"Invalid log file path: {log_path}")
