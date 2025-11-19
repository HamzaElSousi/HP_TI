"""
Structured Logging Infrastructure for HP_TI

Provides JSON-formatted structured logging with support for contextual
information and multiple output formats.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import json


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Formats log records as JSON with ISO8601 timestamps and contextual fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add standard fields from record
        if hasattr(record, "component"):
            log_data["component"] = record.component
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "source_ip"):
            log_data["source_ip"] = record.source_ip
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for development.

    Formats logs in a readable format with colors (when supported).
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        """
        Initialize text formatter.

        Args:
            use_colors: Whether to use ANSI colors
        """
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as colored text.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Base message
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        name = record.name
        message = record.getMessage()

        # Apply color if enabled
        if self.use_colors:
            color = self.COLORS.get(level, "")
            level = f"{color}{level}{self.RESET}"

        # Build formatted message
        formatted = f"{timestamp} [{level}] {name}: {message}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        # Add extra context if present
        if hasattr(record, "source_ip"):
            formatted += f" [ip={record.source_ip}]"
        if hasattr(record, "session_id"):
            formatted += f" [session={record.session_id}]"

        return formatted


def setup_logger(
    name: str,
    level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Set up a logger with appropriate handlers and formatters.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'text')
        log_file: Optional file path for file logging

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger("honeypot.ssh", level="INFO", log_format="json")
        >>> logger.info("SSH connection", extra={"source_ip": "192.168.1.1"})
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Choose formatter
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())  # Always use JSON for files
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_honeypot_logger(
    service: str, log_dir: Path, level: str = "INFO", log_format: str = "json"
) -> logging.Logger:
    """
    Get a logger configured for a honeypot service.

    Args:
        service: Service name (e.g., 'ssh', 'http')
        log_dir: Directory for log files
        level: Log level
        log_format: Format type

    Returns:
        Configured logger instance
    """
    logger_name = f"honeypot.{service}"
    log_file = log_dir / f"{service}_honeypot.log"

    return setup_logger(
        name=logger_name, level=level, log_format=log_format, log_file=log_file
    )


class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter that adds contextual information to all log messages.

    Useful for adding session-specific or request-specific context.
    """

    def process(
        self, msg: str, kwargs: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Process log message and add extra context.

        Args:
            msg: Log message
            kwargs: Keyword arguments

        Returns:
            Tuple of (message, kwargs) with added context
        """
        # Merge adapter extra fields with message extra fields
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra

        return msg, kwargs


def create_session_logger(
    base_logger: logging.Logger, session_id: str, source_ip: str
) -> LoggerAdapter:
    """
    Create a logger adapter with session context.

    Args:
        base_logger: Base logger to adapt
        session_id: Session identifier
        source_ip: Source IP address

    Returns:
        Logger adapter with session context

    Example:
        >>> base = setup_logger("honeypot.ssh")
        >>> session_logger = create_session_logger(base, "session-123", "192.168.1.1")
        >>> session_logger.info("Authentication attempt")  # Includes session ID and IP
    """
    return LoggerAdapter(
        base_logger, {"session_id": session_id, "source_ip": source_ip}
    )
