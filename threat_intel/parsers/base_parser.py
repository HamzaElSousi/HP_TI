"""
Base parser class for HP_TI log parsers.

Provides common functionality for parsing honeypot logs and extracting
structured data.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ParsedLogEntry(BaseModel):
    """
    Base model for parsed log entries.

    Uses Pydantic for validation and type safety.
    """

    timestamp: datetime
    level: str
    component: str
    message: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v):
        """Parse timestamp from string if needed."""
        if isinstance(v, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                # Try other common formats
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f",
                ]
                for fmt in formats:
                    try:
                        return datetime.strptime(v, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Could not parse timestamp: {v}")
        return v


class SSHLogEntry(ParsedLogEntry):
    """Parsed SSH honeypot log entry with specific fields."""

    event_type: str
    session_id: Optional[str] = None
    source_ip: Optional[str] = None
    source_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    command: Optional[str] = None
    auth_method: Optional[str] = None
    success: Optional[bool] = None


class BaseParser(ABC):
    """
    Abstract base class for log parsers.

    Subclasses must implement the parse_line method.
    """

    def __init__(self, service_name: str):
        """
        Initialize parser.

        Args:
            service_name: Name of the honeypot service
        """
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.{service_name}")

    @abstractmethod
    def parse_line(self, line: str) -> Optional[ParsedLogEntry]:
        """
        Parse a single log line.

        Args:
            line: Raw log line

        Returns:
            Parsed log entry or None if parsing failed
        """
        pass

    def parse_file(self, file_path: str) -> List[ParsedLogEntry]:
        """
        Parse an entire log file.

        Args:
            file_path: Path to log file

        Returns:
            List of parsed log entries
        """
        entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = self.parse_line(line)
                    if entry:
                        entries.append(entry)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse line {line_num}: {e}", exc_info=True
                    )
                    continue

        self.logger.info(f"Parsed {len(entries)} entries from {file_path}")
        return entries

    def parse_json_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a JSON log line.

        Args:
            line: JSON string

        Returns:
            Parsed dictionary or None if invalid JSON
        """
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON: {e}")
            return None

    def validate_required_fields(
        self, data: Dict[str, Any], required_fields: List[str]
    ) -> bool:
        """
        Check if all required fields are present.

        Args:
            data: Data dictionary
            required_fields: List of required field names

        Returns:
            True if all required fields present, False otherwise
        """
        for field in required_fields:
            if field not in data:
                self.logger.debug(f"Missing required field: {field}")
                return False
        return True

    def sanitize_string(self, value: str, max_length: int = 10000) -> str:
        """
        Sanitize string value to prevent log injection and limit size.

        Args:
            value: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        # Remove control characters except newline and tab
        sanitized = "".join(
            char for char in value if char.isprintable() or char in "\n\t"
        )

        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "...[truncated]"

        return sanitized

    def extract_ip_port(self, addr_string: str) -> tuple[Optional[str], Optional[int]]:
        """
        Extract IP and port from address string.

        Args:
            addr_string: Address string (e.g., "192.168.1.1:12345")

        Returns:
            Tuple of (ip, port)
        """
        try:
            if ":" in addr_string:
                ip, port = addr_string.rsplit(":", 1)
                return ip, int(port)
            else:
                return addr_string, None
        except (ValueError, AttributeError):
            return None, None
