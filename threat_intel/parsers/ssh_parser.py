"""
SSH log parser for HP_TI.

Parses SSH honeypot logs and extracts structured data for storage
and analysis.
"""

import logging
from typing import Optional, Dict, Any
from threat_intel.parsers.base_parser import BaseParser, SSHLogEntry

logger = logging.getLogger(__name__)


class SSHParser(BaseParser):
    """
    Parser for SSH honeypot logs.

    Handles JSON-formatted SSH honeypot logs and extracts relevant fields.
    """

    def __init__(self):
        """Initialize SSH parser."""
        super().__init__("ssh")

    def parse_line(self, line: str) -> Optional[SSHLogEntry]:
        """
        Parse a single SSH log line.

        Args:
            line: Raw log line (JSON format)

        Returns:
            Parsed SSH log entry or None if parsing failed
        """
        # Parse JSON
        data = self.parse_json_line(line)
        if not data:
            return None

        # Validate required fields
        if not self.validate_required_fields(
            data, ["timestamp", "level", "message"]
        ):
            return None

        try:
            # Build entry with all available fields
            entry_data = {
                "timestamp": data["timestamp"],
                "level": data["level"],
                "component": data.get("component", "ssh_honeypot"),
                "message": self.sanitize_string(data["message"]),
                "event_type": data.get("event_type", "unknown"),
                "raw_data": data,
            }

            # Add optional fields if present
            optional_fields = [
                "session_id",
                "source_ip",
                "source_port",
                "username",
                "password",
                "command",
                "auth_method",
                "success",
            ]

            for field in optional_fields:
                if field in data:
                    entry_data[field] = data[field]

            # Create and validate entry
            entry = SSHLogEntry(**entry_data)
            return entry

        except Exception as e:
            self.logger.warning(f"Error creating log entry: {e}")
            return None

    def extract_auth_attempt(self, entry: SSHLogEntry) -> Optional[Dict[str, Any]]:
        """
        Extract authentication attempt data from log entry.

        Args:
            entry: Parsed log entry

        Returns:
            Dictionary with auth attempt data or None
        """
        if entry.event_type != "auth_attempt":
            return None

        return {
            "session_id": entry.session_id,
            "timestamp": entry.timestamp,
            "username": entry.username,
            "password": entry.password,
            "auth_method": entry.auth_method,
            "success": entry.success,
            "source_ip": entry.source_ip,
        }

    def extract_command(self, entry: SSHLogEntry) -> Optional[Dict[str, Any]]:
        """
        Extract command execution data from log entry.

        Args:
            entry: Parsed log entry

        Returns:
            Dictionary with command data or None
        """
        if entry.event_type not in ["command_received", "command_exec"]:
            return None

        return {
            "session_id": entry.session_id,
            "timestamp": entry.timestamp,
            "command": entry.command,
            "source_ip": entry.source_ip,
        }

    def extract_session_event(self, entry: SSHLogEntry) -> Optional[Dict[str, Any]]:
        """
        Extract session event data from log entry.

        Args:
            entry: Parsed log entry

        Returns:
            Dictionary with session event data or None
        """
        if entry.event_type not in [
            "connection_attempt",
            "session_ended",
            "honeypot_started",
        ]:
            return None

        event_data = {
            "session_id": entry.session_id,
            "timestamp": entry.timestamp,
            "event_type": entry.event_type,
            "source_ip": entry.source_ip,
            "source_port": entry.source_port,
        }

        # Add any additional data from raw_data
        if "session_data" in entry.raw_data:
            event_data["session_data"] = entry.raw_data["session_data"]

        return event_data

    def categorize_entry(self, entry: SSHLogEntry) -> str:
        """
        Categorize log entry by type.

        Args:
            entry: Parsed log entry

        Returns:
            Category string
        """
        event_type = entry.event_type

        if event_type == "auth_attempt":
            return "authentication"
        elif event_type in ["command_received", "command_exec"]:
            return "command"
        elif event_type in ["connection_attempt", "session_ended"]:
            return "session"
        elif event_type in ["honeypot_started", "honeypot_stopped"]:
            return "system"
        else:
            return "other"
