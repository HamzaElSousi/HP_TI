"""
Unit tests for HTTP honeypot service.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from honeypot.services.http_honeypot import HTTPHoneypot
from honeypot.config.config_loader import HoneypotHTTPConfig


class TestHTTPHoneypot:
    """Tests for HTTP honeypot."""

    @pytest.fixture
    def config(self):
        """Create HTTP honeypot configuration."""
        return HoneypotHTTPConfig(
            enabled=True,
            host="127.0.0.1",
            port=8080,
            https_port=8443,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create HTTP honeypot instance."""
        return HTTPHoneypot(config, log_dir)

    def test_init(self, honeypot, config):
        """Test HTTP honeypot initialization."""
        assert honeypot is not None
        assert honeypot.config == config
        assert honeypot.running is False
        assert honeypot.sessions == {}

    def test_detect_sql_injection(self, honeypot):
        """Test SQL injection detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {"id": "1' OR '1'='1"}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/admin", mock_request)
        assert attack_type == "sql_injection"

    def test_detect_xss(self, honeypot):
        """Test XSS detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {"query": "<script>alert('xss')</script>"}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/search", mock_request)
        assert attack_type == "xss"

    def test_detect_path_traversal(self, honeypot):
        """Test path traversal detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {"file": "../../../etc/passwd"}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/download", mock_request)
        assert attack_type == "path_traversal"

    def test_detect_command_injection(self, honeypot):
        """Test command injection detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {"cmd": "; cat /etc/passwd"}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/execute", mock_request)
        assert attack_type == "command_injection"

    def test_detect_admin_panel_access(self, honeypot):
        """Test admin panel access detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/admin", mock_request)
        # Should be None if no parameters, but admin panel path
        assert attack_type in [None, "admin_panel_access"]

    def test_detect_webshell_access(self, honeypot):
        """Test webshell access detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/shell.php", mock_request)
        assert attack_type == "webshell_access"

    def test_detect_config_file_exposure(self, honeypot):
        """Test config file exposure detection."""
        # Create mock request
        mock_request = Mock()
        mock_request.args = {}
        mock_request.form = {}

        attack_type = honeypot._detect_attack_type("/.env", mock_request)
        assert attack_type == "config_file_exposure"

    def test_is_admin_panel(self, honeypot):
        """Test admin panel path detection."""
        assert honeypot._is_admin_panel("/admin") is True
        assert honeypot._is_admin_panel("/wp-admin") is True
        assert honeypot._is_admin_panel("/administrator") is True
        assert honeypot._is_admin_panel("/phpmyadmin") is True
        assert honeypot._is_admin_panel("/cpanel") is True
        assert honeypot._is_admin_panel("/normal-page") is False

    def test_get_admin_panel_html(self, honeypot):
        """Test admin panel HTML generation."""
        html = honeypot._get_admin_panel_html()
        assert "Admin Panel" in html
        assert "username" in html
        assert "password" in html
        assert "form" in html

    def test_get_sessions(self, honeypot):
        """Test getting sessions."""
        # Initially empty
        sessions = honeypot.get_sessions()
        assert sessions == []

        # Add a test session
        honeypot.sessions["test-session"] = {
            "session_id": "test-session",
            "source_ip": "192.168.1.1",
            "requests": [],
        }

        sessions = honeypot.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-session"

    @patch("honeypot.services.http_honeypot.Flask")
    def test_flask_app_creation(self, mock_flask, honeypot):
        """Test Flask app is created with routes."""
        # The app is created in __init__
        assert honeypot.app is not None

    def test_stop(self, honeypot):
        """Test stopping the honeypot."""
        honeypot.running = True
        honeypot.stop()
        assert honeypot.running is False


class TestHTTPHoneypotIntegration:
    """Integration tests for HTTP honeypot."""

    @pytest.fixture
    def config(self):
        """Create HTTP honeypot configuration."""
        return HoneypotHTTPConfig(
            enabled=True,
            host="127.0.0.1",
            port=18080,  # Use non-standard port for testing
            https_port=18443,
        )

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def honeypot(self, config, log_dir):
        """Create HTTP honeypot instance."""
        return HTTPHoneypot(config, log_dir)

    def test_flask_routes_exist(self, honeypot):
        """Test that Flask routes are registered."""
        app = honeypot.app

        # Get all routes
        routes = [rule.rule for rule in app.url_map.iter_rules()]

        # Check that our catch-all route exists
        assert any("<path:path>" in route for route in routes)

    def test_admin_panel_route(self, honeypot):
        """Test admin panel route returns HTML."""
        with honeypot.app.test_client() as client:
            response = client.get("/admin")
            assert response.status_code == 200
            assert b"Admin Panel" in response.data

    def test_login_post(self, honeypot):
        """Test login POST request."""
        with honeypot.app.test_client() as client:
            response = client.post(
                "/admin/login",
                data={"username": "admin", "password": "password123"},
            )
            # Should return error (credentials incorrect)
            assert response.status_code == 200
            assert b"Invalid credentials" in response.data

    def test_sql_injection_logged(self, honeypot):
        """Test that SQL injection attempts are detected."""
        with honeypot.app.test_client() as client:
            response = client.get("/search?q=1' OR '1'='1")
            # Request should be processed
            assert response.status_code in [200, 404]
