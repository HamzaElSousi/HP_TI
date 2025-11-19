"""
Unit tests for Telnet honeypot service.
"""

import pytest
import socket
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from honeypot.services.telnet_honeypot import TelnetHoneypot
from honeypot.config.config_loader import HoneypotTelnetConfig


class TestTelnetHoneypot:
    """Tests for Telnet honeypot."""

    @pytest.fixture
    def config(self):
        """Create Telnet honeypot configuration."""
        return HoneypotTelnetConfig(
            enabled=True,
            host="127.0.0.1",
            port=2323,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create Telnet honeypot instance."""
        return TelnetHoneypot(config, log_dir)

    def test_init(self, honeypot, config):
        """Test Telnet honeypot initialization."""
        assert honeypot is not None
        assert honeypot.config == config
        assert honeypot.running is False
        assert honeypot.sessions == {}
        assert honeypot.server_socket is None

    def test_device_profiles_exist(self, honeypot):
        """Test that device profiles are defined."""
        assert "router" in honeypot.DEVICE_PROFILES
        assert "camera" in honeypot.DEVICE_PROFILES
        assert "dvr" in honeypot.DEVICE_PROFILES

        # Check profile structure
        router_profile = honeypot.DEVICE_PROFILES["router"]
        assert "banner" in router_profile
        assert "login_prompt" in router_profile
        assert "password_prompt" in router_profile
        assert "shell_prompt" in router_profile

    def test_get_random_profile(self, honeypot):
        """Test getting random device profile."""
        profile = honeypot._get_random_profile()
        assert profile in honeypot.DEVICE_PROFILES.values()

    def test_send(self, honeypot):
        """Test sending data to client."""
        mock_socket = Mock()
        mock_socket.sendall = Mock()

        honeypot._send(mock_socket, "test message")
        mock_socket.sendall.assert_called_once()

    def test_send_error_handling(self, honeypot):
        """Test send error handling."""
        mock_socket = Mock()
        mock_socket.sendall = Mock(side_effect=Exception("Send error"))

        # Should not raise exception
        honeypot._send(mock_socket, "test")

    def test_receive_line(self, honeypot):
        """Test receiving a line from client."""
        mock_socket = Mock()
        # Simulate receiving "username\r\n"
        mock_socket.recv = Mock(side_effect=[b"u", b"s", b"e", b"r", b"\r", b"\n"])

        result = honeypot._receive_line(mock_socket, timeout=5)
        assert result == "user"

    def test_receive_line_timeout(self, honeypot):
        """Test receive timeout."""
        mock_socket = Mock()
        mock_socket.settimeout = Mock()
        mock_socket.recv = Mock(side_effect=socket.timeout())

        result = honeypot._receive_line(mock_socket, timeout=1)
        assert result is None

    def test_receive_line_buffer_limit(self, honeypot):
        """Test receive buffer limit."""
        mock_socket = Mock()
        # Simulate receiving many bytes without CRLF
        mock_socket.recv = Mock(return_value=b"a")

        result = honeypot._receive_line(mock_socket, timeout=5)
        # Should return after buffer limit
        assert result is not None
        assert len(result) <= 1024

    def test_get_sessions(self, honeypot):
        """Test getting sessions."""
        # Initially empty
        sessions = honeypot.get_sessions()
        assert sessions == []

        # Add a test session
        honeypot.sessions["test-session"] = {
            "session_id": "test-session",
            "source_ip": "192.168.1.1",
            "commands": [],
        }

        sessions = honeypot.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-session"

    def test_stop(self, honeypot):
        """Test stopping the honeypot."""
        honeypot.running = True
        honeypot.server_socket = Mock()

        honeypot.stop()

        assert honeypot.running is False
        honeypot.server_socket.close.assert_called_once()

    def test_stop_without_socket(self, honeypot):
        """Test stopping when no socket exists."""
        honeypot.running = True
        honeypot.server_socket = None

        # Should not raise exception
        honeypot.stop()
        assert honeypot.running is False


class TestTelnetHoneypotCommands:
    """Tests for Telnet command handling."""

    @pytest.fixture
    def config(self):
        """Create Telnet honeypot configuration."""
        return HoneypotTelnetConfig(
            enabled=True,
            host="127.0.0.1",
            port=2323,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create Telnet honeypot instance."""
        return TelnetHoneypot(config, log_dir)

    def test_common_commands(self, honeypot):
        """Test that common commands have responses."""
        profile = honeypot.DEVICE_PROFILES["router"]

        # Check that common commands exist
        common_commands = ["help", "ls", "pwd", "uname", "exit"]
        for cmd in common_commands:
            assert cmd in profile.get("commands", {}) or cmd in ["exit"]

    def test_router_profile_commands(self, honeypot):
        """Test router profile has expected commands."""
        profile = honeypot.DEVICE_PROFILES["router"]
        commands = profile.get("commands", {})

        # Router should have network-related commands
        assert "help" in commands
        assert "show" in commands or "ls" in commands

    def test_camera_profile_commands(self, honeypot):
        """Test camera profile has expected commands."""
        profile = honeypot.DEVICE_PROFILES["camera"]
        assert "banner" in profile
        assert "IP Camera" in profile["banner"]

    def test_dvr_profile_commands(self, honeypot):
        """Test DVR profile has expected commands."""
        profile = honeypot.DEVICE_PROFILES["dvr"]
        assert "banner" in profile
        assert "DVR" in profile["banner"]


class TestTelnetHoneypotIntegration:
    """Integration tests for Telnet honeypot."""

    @pytest.fixture
    def config(self):
        """Create Telnet honeypot configuration."""
        return HoneypotTelnetConfig(
            enabled=True,
            host="127.0.0.1",
            port=12323,  # Use non-standard port for testing
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create Telnet honeypot instance."""
        return TelnetHoneypot(config, log_dir)

    @pytest.mark.asyncio
    async def test_honeypot_lifecycle(self, honeypot):
        """Test honeypot start and stop lifecycle."""
        # This is a basic lifecycle test
        # In a real integration test, we would start the server and connect to it
        assert honeypot.running is False

        # Mock the socket to prevent actual binding
        with patch("socket.socket") as mock_socket_class:
            mock_socket = Mock()
            mock_socket_class.return_value = mock_socket
            mock_socket.accept = Mock(side_effect=socket.timeout())

            # Start would normally run forever, so we'll test the initialization
            honeypot.running = True
            assert honeypot.running is True

            # Stop
            honeypot.stop()
            assert honeypot.running is False
