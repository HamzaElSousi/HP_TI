"""
Unit tests for SSH log parser.
"""

import pytest
import json
from datetime import datetime
from threat_intel.parsers.ssh_parser import SSHParser


class TestSSHParser:
    """Tests for SSH log parser."""

    @pytest.fixture
    def parser(self):
        """Create SSH parser instance."""
        return SSHParser()

    @pytest.fixture
    def sample_auth_log(self):
        """Sample authentication attempt log entry."""
        return json.dumps({
            "timestamp": "2025-11-19T12:30:45.123Z",
            "level": "INFO",
            "component": "ssh_honeypot",
            "message": "SSH authentication attempt",
            "event_type": "auth_attempt",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "source_ip": "192.168.1.100",
            "source_port": 54321,
            "username": "root",
            "password": "admin123",
            "auth_method": "password",
            "success": False
        })

    @pytest.fixture
    def sample_command_log(self):
        """Sample command execution log entry."""
        return json.dumps({
            "timestamp": "2025-11-19T12:31:00.456Z",
            "level": "INFO",
            "component": "ssh_honeypot",
            "message": "Command received: whoami",
            "event_type": "command_received",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "source_ip": "192.168.1.100",
            "command": "whoami"
        })

    def test_parse_auth_attempt(self, parser, sample_auth_log):
        """Test parsing authentication attempt log."""
        entry = parser.parse_line(sample_auth_log)

        assert entry is not None
        assert entry.event_type == "auth_attempt"
        assert entry.username == "root"
        assert entry.password == "admin123"
        assert entry.auth_method == "password"
        assert entry.success is False
        assert entry.source_ip == "192.168.1.100"
        assert entry.source_port == 54321

    def test_parse_command(self, parser, sample_command_log):
        """Test parsing command execution log."""
        entry = parser.parse_line(sample_command_log)

        assert entry is not None
        assert entry.event_type == "command_received"
        assert entry.command == "whoami"
        assert entry.source_ip == "192.168.1.100"

    def test_parse_invalid_json(self, parser):
        """Test parsing invalid JSON."""
        entry = parser.parse_line("not valid json {{{")

        assert entry is None

    def test_parse_missing_required_fields(self, parser):
        """Test parsing log with missing required fields."""
        log = json.dumps({"level": "INFO"})  # Missing timestamp and message

        entry = parser.parse_line(log)

        assert entry is None

    def test_extract_auth_attempt(self, parser, sample_auth_log):
        """Test extracting auth attempt data."""
        entry = parser.parse_line(sample_auth_log)
        auth_data = parser.extract_auth_attempt(entry)

        assert auth_data is not None
        assert auth_data["username"] == "root"
        assert auth_data["password"] == "admin123"
        assert auth_data["auth_method"] == "password"

    def test_extract_command(self, parser, sample_command_log):
        """Test extracting command data."""
        entry = parser.parse_line(sample_command_log)
        cmd_data = parser.extract_command(entry)

        assert cmd_data is not None
        assert cmd_data["command"] == "whoami"

    def test_categorize_auth_entry(self, parser, sample_auth_log):
        """Test categorizing authentication entry."""
        entry = parser.parse_line(sample_auth_log)
        category = parser.categorize_entry(entry)

        assert category == "authentication"

    def test_categorize_command_entry(self, parser, sample_command_log):
        """Test categorizing command entry."""
        entry = parser.parse_line(sample_command_log)
        category = parser.categorize_entry(entry)

        assert category == "command"


class TestBaseParser:
    """Tests for base parser functionality."""

    @pytest.fixture
    def parser(self):
        """Create SSH parser instance."""
        return SSHParser()

    def test_sanitize_string(self, parser):
        """Test string sanitization."""
        # Test normal string
        assert parser.sanitize_string("hello world") == "hello world"

        # Test with control characters
        dangerous = "hello\x00\x01world"
        sanitized = parser.sanitize_string(dangerous)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized

        # Test truncation
        long_string = "a" * 20000
        sanitized = parser.sanitize_string(long_string, max_length=100)
        assert len(sanitized) <= 120  # 100 + truncation message

    def test_extract_ip_port(self, parser):
        """Test IP and port extraction."""
        ip, port = parser.extract_ip_port("192.168.1.1:12345")

        assert ip == "192.168.1.1"
        assert port == 12345

    def test_extract_ip_only(self, parser):
        """Test IP extraction without port."""
        ip, port = parser.extract_ip_port("192.168.1.1")

        assert ip == "192.168.1.1"
        assert port is None
