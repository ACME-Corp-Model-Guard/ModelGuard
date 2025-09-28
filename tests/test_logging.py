"""
Tests for the logging_utils module.
"""
import logging
import os
import tempfile
from logging import handlers
from pathlib import Path

import pytest

from src.logging_utils import _SILENT_SENTINEL, _parse_level, setup_logging


def test_parse_level_none():
    """Test parsing None log level."""
    assert _parse_level(None) is None


def test_parse_level_off():
    """Test parsing 'off' log level."""
    for val in ["off", "OFF", "Off", "none", "NONE", "silent", "0"]:
        assert _parse_level(val) == _SILENT_SENTINEL


def test_parse_level_numbers():
    """Test parsing numeric log levels."""
    assert _parse_level("1") == logging.INFO
    assert _parse_level("2") == logging.DEBUG


def test_parse_level_names():
    """Test parsing named log levels."""
    assert _parse_level("info") == logging.INFO
    assert _parse_level("debug") == logging.DEBUG
    assert _parse_level("warning") == logging.WARNING
    assert _parse_level("error") == logging.ERROR
    assert _parse_level("critical") == logging.CRITICAL


def test_parse_level_invalid():
    """Test parsing invalid log level defaults to INFO."""
    assert _parse_level("invalid_level") == logging.INFO


def test_setup_logging_silent():
    """Test setup_logging with silent level."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "test.log"
        os.environ["LOG_LEVEL"] = "silent"
        os.environ["LOG_FILE"] = str(log_file)
        
        # Save the original handlers to restore later
        logger = logging.getLogger()
        original_handlers = list(logger.handlers)
        
        try:
            setup_logging()
            
            # Check that file was created but is empty
            assert log_file.exists()
            assert log_file.stat().st_size == 0
        finally:
            # Restore original handlers
            logger.handlers = original_handlers


def test_setup_logging_with_valid_file():
    """Test setup_logging with a valid log file path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "test.log"
        os.environ["LOG_LEVEL"] = "info"
        os.environ["LOG_FILE"] = str(log_file)
        
        # Save the original handlers to restore later
        logger = logging.getLogger()
        original_handlers = list(logger.handlers)
        original_level = logger.level
        
        try:
            setup_logging()
            
            # Check that log file was created
            assert log_file.exists()
            
            # Check that logger was set to INFO level
            assert logger.level == logging.INFO
        finally:
            # Restore original settings
            logger.handlers = original_handlers
            logger.level = original_level


def test_setup_logging_with_invalid_file():
    """Test setup_logging with an invalid log file path."""
    os.environ["LOG_LEVEL"] = "info"
    os.environ["LOG_FILE"] = "/path/that/cannot/exist/test.log"
    
    # Save the original handlers to restore later
    logger = logging.getLogger()
    original_handlers = list(logger.handlers)
    original_level = logger.level
    
    try:
        setup_logging()
        
        # Check that logger was set to INFO level
        assert logger.level == logging.INFO
    finally:
        # Restore original settings
        logger.handlers = original_handlers
        logger.level = original_level