"""
Unit tests for logging infrastructure.
"""

import pytest
import json
from pathlib import Path
from honeypot.logging.logger import (
    JSONFormatter,
    TextFormatter,
    setup_logger,
    get_honeypot_logger,
    create_session_logger,
)


class TestJSONFormatter:
    """Tests for JSON log formatter."""

    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["logger"] == "test_logger"
        assert "timestamp" in log_data

    def test_format_with_extra_fields(self):
        """Test formatting with extra contextual fields."""
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.source_ip = "192.168.1.1"
        record.session_id = "test-session-123"

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["source_ip"] == "192.168.1.1"
        assert log_data["session_id"] == "test-session-123"


class TestTextFormatter:
    """Tests for text log formatter."""

    def test_format_basic_message(self):
        """Test formatting a basic text message."""
        import logging

        formatter = TextFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert "INFO" in formatted
        assert "test_logger" in formatted
        assert "Test message" in formatted


class TestSetupLogger:
    """Tests for logger setup."""

    def test_setup_logger_default(self):
        """Test logger setup with default parameters."""
        logger = setup_logger("test.logger")

        assert logger.name == "test.logger"
        assert logger.level == 20  # INFO level
        assert len(logger.handlers) > 0

    def test_setup_logger_with_level(self):
        """Test logger setup with custom level."""
        logger = setup_logger("test.logger.debug", level="DEBUG")

        assert logger.level == 10  # DEBUG level

    def test_setup_logger_json_format(self):
        """Test logger setup with JSON format."""
        logger = setup_logger("test.logger.json", log_format="json")

        # Check that a JSON formatter is being used
        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logger_text_format(self):
        """Test logger setup with text format."""
        logger = setup_logger("test.logger.text", log_format="text")

        # Check that a text formatter is being used
        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, TextFormatter)


class TestGetHoneypotLogger:
    """Tests for honeypot logger creation."""

    def test_get_honeypot_logger(self, tmp_path):
        """Test creating a honeypot logger."""
        log_dir = tmp_path / "logs"
        logger = get_honeypot_logger("ssh", log_dir)

        assert logger.name == "honeypot.ssh"
        assert len(logger.handlers) > 0

        # Check that log directory was created
        assert log_dir.exists()


class TestCreateSessionLogger:
    """Tests for session logger adapter."""

    def test_create_session_logger(self):
        """Test creating a session logger with context."""
        base_logger = setup_logger("test.session")
        session_logger = create_session_logger(
            base_logger, "session-123", "192.168.1.1"
        )

        assert session_logger.extra["session_id"] == "session-123"
        assert session_logger.extra["source_ip"] == "192.168.1.1"
