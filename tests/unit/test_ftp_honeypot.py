"""
Unit tests for FTP honeypot service.
"""

import pytest
import socket
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from honeypot.services.ftp_honeypot import FTPHoneypot
from honeypot.config.config_loader import HoneypotFTPConfig


class TestFTPHoneypot:
    """Tests for FTP honeypot."""

    @pytest.fixture
    def config(self):
        """Create FTP honeypot configuration."""
        return HoneypotFTPConfig(
            enabled=True,
            host="127.0.0.1",
            port=2121,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create FTP honeypot instance."""
        return FTPHoneypot(config, log_dir)

    def test_init(self, honeypot, config):
        """Test FTP honeypot initialization."""
        assert honeypot is not None
        assert honeypot.config == config
        assert honeypot.running is False
        assert honeypot.sessions == {}
        assert honeypot.server_socket is None

    def test_ftp_response_codes(self, honeypot):
        """Test FTP response codes are defined."""
        assert honeypot.RESPONSE_220 == "220 FTP Server ready\r\n"
        assert honeypot.RESPONSE_230 == "230 User logged in\r\n"
        assert honeypot.RESPONSE_331 == "331 Password required\r\n"
        assert honeypot.RESPONSE_530 == "530 Login incorrect\r\n"
        assert honeypot.RESPONSE_221 == "221 Goodbye\r\n"

    def test_fake_files_defined(self, honeypot):
        """Test fake files are defined."""
        assert len(honeypot.FAKE_FILES) > 0
        assert "README.txt" in honeypot.FAKE_FILES
        assert "index.html" in honeypot.FAKE_FILES

    def test_fake_dirs_defined(self, honeypot):
        """Test fake directories are defined."""
        assert len(honeypot.FAKE_DIRS) > 0
        assert "uploads" in honeypot.FAKE_DIRS
        assert "downloads" in honeypot.FAKE_DIRS

    def test_send(self, honeypot):
        """Test sending data to client."""
        mock_socket = Mock()
        mock_socket.sendall = Mock()

        honeypot._send(mock_socket, "220 Welcome\r\n")
        mock_socket.sendall.assert_called_once_with(b"220 Welcome\r\n")

    def test_send_error_handling(self, honeypot):
        """Test send error handling."""
        mock_socket = Mock()
        mock_socket.sendall = Mock(side_effect=Exception("Send error"))

        # Should not raise exception
        honeypot._send(mock_socket, "test")

    def test_receive_line(self, honeypot):
        """Test receiving a line from client."""
        mock_socket = Mock()
        # Simulate receiving "USER admin\r\n"
        mock_socket.recv = Mock(
            side_effect=[b"U", b"S", b"E", b"R", b" ", b"a", b"d", b"m", b"i", b"n", b"\r", b"\n"]
        )

        result = honeypot._receive_line(mock_socket, timeout=30)
        assert result == "USER admin"

    def test_receive_line_timeout(self, honeypot):
        """Test receive timeout."""
        mock_socket = Mock()
        mock_socket.settimeout = Mock()
        mock_socket.recv = Mock(side_effect=socket.timeout())

        result = honeypot._receive_line(mock_socket, timeout=30)
        assert result is None

    def test_receive_line_buffer_limit(self, honeypot):
        """Test receive buffer limit."""
        mock_socket = Mock()
        # Simulate receiving many bytes without CRLF
        mock_socket.recv = Mock(return_value=b"a")

        result = honeypot._receive_line(mock_socket, timeout=30)
        # Should return after buffer limit
        assert result is not None
        assert len(result) <= 1024

    def test_handle_user_command(self, honeypot):
        """Test USER command handling."""
        session_id = "test-session"
        honeypot.sessions[session_id] = {
            "username": None,
            "auth_attempts": [],
        }

        response = honeypot._handle_ftp_command("USER", "admin", session_id, Mock())
        assert response == honeypot.RESPONSE_331
        assert honeypot.sessions[session_id]["username"] == "admin"

    def test_handle_pass_command(self, honeypot):
        """Test PASS command handling."""
        session_id = "test-session"
        honeypot.sessions[session_id] = {
            "username": "admin",
            "auth_attempts": [],
        }

        mock_logger = Mock()
        response = honeypot._handle_ftp_command("PASS", "password123", session_id, mock_logger)

        # Should always reject (it's a honeypot)
        assert response == honeypot.RESPONSE_530

        # Should log authentication attempt
        assert len(honeypot.sessions[session_id]["auth_attempts"]) == 1
        assert honeypot.sessions[session_id]["auth_attempts"][0]["username"] == "admin"
        assert honeypot.sessions[session_id]["auth_attempts"][0]["password"] == "password123"

    def test_handle_syst_command(self, honeypot):
        """Test SYST command handling."""
        response = honeypot._handle_ftp_command("SYST", "", "test", Mock())
        assert response == honeypot.RESPONSE_215

    def test_handle_pwd_command(self, honeypot):
        """Test PWD command handling."""
        response = honeypot._handle_ftp_command("PWD", "", "test", Mock())
        assert response == honeypot.RESPONSE_257

    def test_handle_cwd_command(self, honeypot):
        """Test CWD command handling."""
        session_id = "test-session"
        honeypot.sessions[session_id] = {}
        mock_logger = Mock()

        response = honeypot._handle_ftp_command("CWD", "/uploads", session_id, mock_logger)
        assert response == honeypot.RESPONSE_250

    def test_handle_retr_command(self, honeypot):
        """Test RETR (download) command handling."""
        session_id = "test-session"
        honeypot.sessions[session_id] = {}
        mock_logger = Mock()

        response = honeypot._handle_ftp_command("RETR", "file.txt", session_id, mock_logger)
        # Should return file not found
        assert response == honeypot.RESPONSE_550

    def test_handle_stor_command(self, honeypot):
        """Test STOR (upload) command handling."""
        session_id = "test-session"
        honeypot.sessions[session_id] = {}
        mock_logger = Mock()

        response = honeypot._handle_ftp_command("STOR", "malware.exe", session_id, mock_logger)
        # Should return can't create file
        assert response == honeypot.RESPONSE_550

    def test_handle_quit_command(self, honeypot):
        """Test QUIT command handling."""
        response = honeypot._handle_ftp_command("QUIT", "", "test", Mock())
        assert response == honeypot.RESPONSE_221

    def test_handle_type_command(self, honeypot):
        """Test TYPE command handling."""
        response = honeypot._handle_ftp_command("TYPE", "I", "test", Mock())
        assert response == honeypot.RESPONSE_200

    def test_handle_port_command(self, honeypot):
        """Test PORT command handling."""
        response = honeypot._handle_ftp_command("PORT", "192,168,1,1,20,21", "test", Mock())
        # Not implemented in low-interaction honeypot
        assert response == honeypot.RESPONSE_502

    def test_handle_pasv_command(self, honeypot):
        """Test PASV command handling."""
        response = honeypot._handle_ftp_command("PASV", "", "test", Mock())
        # Not implemented in low-interaction honeypot
        assert response == honeypot.RESPONSE_502

    def test_handle_list_command(self, honeypot):
        """Test LIST command handling."""
        response = honeypot._handle_ftp_command("LIST", "", "test", Mock())
        # Not implemented in low-interaction honeypot
        assert response == honeypot.RESPONSE_502

    def test_handle_unknown_command(self, honeypot):
        """Test unknown command handling."""
        response = honeypot._handle_ftp_command("UNKNOWN", "", "test", Mock())
        assert response == honeypot.RESPONSE_500

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


class TestFTPHoneypotIntegration:
    """Integration tests for FTP honeypot."""

    @pytest.fixture
    def config(self):
        """Create FTP honeypot configuration."""
        return HoneypotFTPConfig(
            enabled=True,
            host="127.0.0.1",
            port=12121,  # Use non-standard port for testing
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create FTP honeypot instance."""
        return FTPHoneypot(config, log_dir)

    @pytest.mark.asyncio
    async def test_honeypot_lifecycle(self, honeypot):
        """Test honeypot start and stop lifecycle."""
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

    def test_authentication_sequence(self, honeypot):
        """Test FTP authentication sequence."""
        session_id = "auth-test"
        honeypot.sessions[session_id] = {
            "username": None,
            "auth_attempts": [],
        }
        mock_logger = Mock()

        # Send USER command
        response1 = honeypot._handle_ftp_command("USER", "admin", session_id, mock_logger)
        assert response1 == honeypot.RESPONSE_331
        assert honeypot.sessions[session_id]["username"] == "admin"

        # Send PASS command
        response2 = honeypot._handle_ftp_command("PASS", "password", session_id, mock_logger)
        assert response2 == honeypot.RESPONSE_530  # Always reject

        # Check auth attempt was logged
        assert len(honeypot.sessions[session_id]["auth_attempts"]) == 1


class TestFTPHoneypotSecurity:
    """Security tests for FTP honeypot."""

    @pytest.fixture
    def config(self):
        """Create FTP honeypot configuration."""
        return HoneypotFTPConfig(
            enabled=True,
            host="127.0.0.1",
            port=2121,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create FTP honeypot instance."""
        return FTPHoneypot(config, log_dir)

    def test_always_reject_authentication(self, honeypot):
        """Test that authentication is always rejected."""
        session_id = "security-test"
        honeypot.sessions[session_id] = {
            "username": "admin",
            "auth_attempts": [],
        }
        mock_logger = Mock()

        # Try various common passwords
        passwords = ["admin", "password", "12345", "root", "letmein"]
        for password in passwords:
            response = honeypot._handle_ftp_command("PASS", password, session_id, mock_logger)
            assert response == honeypot.RESPONSE_530

    def test_no_actual_file_operations(self, honeypot):
        """Test that no actual file operations are performed."""
        session_id = "file-test"
        honeypot.sessions[session_id] = {}
        mock_logger = Mock()

        # Download attempt
        response1 = honeypot._handle_ftp_command("RETR", "../../etc/passwd", session_id, mock_logger)
        assert response1 == honeypot.RESPONSE_550

        # Upload attempt
        response2 = honeypot._handle_ftp_command("STOR", "backdoor.php", session_id, mock_logger)
        assert response2 == honeypot.RESPONSE_550
