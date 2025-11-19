"""
Unit tests for service manager.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from honeypot.service_manager import ServiceManager, ServiceStatus


class TestServiceStatus:
    """Tests for ServiceStatus class."""

    def test_init(self):
        """Test service status initialization."""
        status = ServiceStatus("ssh")
        assert status.name == "ssh"
        assert status.running is False
        assert status.start_time is None
        assert status.stop_time is None
        assert status.error is None
        assert status.task is None

    def test_to_dict(self):
        """Test converting status to dictionary."""
        from datetime import datetime

        status = ServiceStatus("http")
        status.running = True
        status.start_time = datetime.utcnow()

        status_dict = status.to_dict()
        assert status_dict["name"] == "http"
        assert status_dict["running"] is True
        assert status_dict["start_time"] is not None
        assert "uptime_seconds" in status_dict


class TestServiceManager:
    """Tests for ServiceManager class."""

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        with patch("honeypot.service_manager.load_config") as mock:
            config = Mock()
            config.ssh = Mock(enabled=True, host="0.0.0.0", port=2222)
            config.http = Mock(enabled=True, host="0.0.0.0", port=8080)
            config.telnet = Mock(enabled=False, host="0.0.0.0", port=2323)
            config.ftp = Mock(enabled=False, host="0.0.0.0", port=2121)
            mock.return_value = config
            yield config

    @pytest.fixture
    def manager(self, mock_config, log_dir):
        """Create service manager with mocked services."""
        with patch("honeypot.service_manager.SSHHoneypot"), \
             patch("honeypot.service_manager.HTTPHoneypot"), \
             patch("honeypot.service_manager.TelnetHoneypot"), \
             patch("honeypot.service_manager.FTPHoneypot"):
            return ServiceManager(log_dir=log_dir)

    def test_init(self, manager):
        """Test service manager initialization."""
        assert manager is not None
        assert manager.config is not None
        assert manager.services is not None
        assert manager.status is not None
        assert manager.shutdown_requested is False

    def test_init_services(self, manager):
        """Test service initialization."""
        # With mock config, SSH and HTTP should be enabled
        assert "ssh" in manager.services
        assert "http" in manager.services
        assert "telnet" not in manager.services  # Disabled
        assert "ftp" not in manager.services  # Disabled

    def test_get_service_list(self, manager):
        """Test getting service list."""
        services = manager.get_service_list()
        assert isinstance(services, list)
        assert "ssh" in services
        assert "http" in services

    def test_get_status_all(self, manager):
        """Test getting status of all services."""
        status = manager.get_status()
        assert isinstance(status, dict)
        assert "ssh" in status
        assert "http" in status

    def test_get_status_single(self, manager):
        """Test getting status of single service."""
        status = manager.get_status("ssh")
        assert isinstance(status, dict)
        assert status["name"] == "ssh"

    def test_get_status_nonexistent(self, manager):
        """Test getting status of nonexistent service."""
        status = manager.get_status("nonexistent")
        assert "error" in status

    @pytest.mark.asyncio
    async def test_start_service(self, manager):
        """Test starting a single service."""
        # Mock the service
        mock_service = Mock()
        mock_service.start = AsyncMock()
        manager.services["test"] = mock_service
        manager.status["test"] = ServiceStatus("test")

        result = await manager._start_service("test", mock_service)
        assert result is True
        assert manager.status["test"].running is True
        assert manager.status["test"].start_time is not None

    @pytest.mark.asyncio
    async def test_start_service_failure(self, manager):
        """Test starting a service that fails."""
        # Mock the service to raise exception
        mock_service = Mock()
        mock_service.start = AsyncMock(side_effect=Exception("Start failed"))
        manager.services["test"] = mock_service
        manager.status["test"] = ServiceStatus("test")

        result = await manager._start_service("test", mock_service)
        assert result is False
        assert manager.status["test"].running is False
        assert manager.status["test"].error is not None

    @pytest.mark.asyncio
    async def test_stop_service(self, manager):
        """Test stopping a single service."""
        # Mock the service
        mock_service = Mock()
        mock_service.stop = Mock()
        manager.services["test"] = mock_service
        manager.status["test"] = ServiceStatus("test")
        manager.status["test"].running = True
        manager.status["test"].task = AsyncMock()

        await manager._stop_service("test", mock_service)
        assert manager.status["test"].running is False
        assert manager.status["test"].stop_time is not None
        mock_service.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_service(self, manager):
        """Test restarting a service."""
        # Mock the service
        mock_service = Mock()
        mock_service.start = AsyncMock()
        mock_service.stop = Mock()
        manager.services["test"] = mock_service
        manager.status["test"] = ServiceStatus("test")

        result = await manager.restart_service("test")
        assert result is True

    @pytest.mark.asyncio
    async def test_restart_nonexistent_service(self, manager):
        """Test restarting nonexistent service."""
        result = await manager.restart_service("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, manager):
        """Test health check when all services are healthy."""
        # Set all services as running
        for name in manager.status:
            manager.status[name].running = True

        health = await manager.health_check()
        assert health["overall_status"] == "healthy"
        assert len(health["services"]) == len(manager.services)

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, manager):
        """Test health check when some services are unhealthy."""
        # Set one service as not running
        services = list(manager.status.keys())
        if services:
            manager.status[services[0]].running = False

        health = await manager.health_check()
        if len(manager.services) > 1:
            assert health["overall_status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_critical(self, manager):
        """Test health check when all services are unhealthy."""
        # Set all services as not running
        for name in manager.status:
            manager.status[name].running = False

        health = await manager.health_check()
        assert health["overall_status"] == "critical"

    def test_get_statistics(self, manager):
        """Test getting service statistics."""
        # Set some services as running
        if manager.status:
            first_service = list(manager.status.keys())[0]
            manager.status[first_service].running = True

        stats = manager.get_statistics()
        assert "total_services" in stats
        assert "running_services" in stats
        assert "stopped_services" in stats
        assert "services" in stats
        assert stats["total_services"] == len(manager.services)

    def test_get_statistics_with_sessions(self, manager):
        """Test getting statistics with service sessions."""
        # Mock a service with sessions
        if manager.services:
            first_service_name = list(manager.services.keys())[0]
            mock_service = manager.services[first_service_name]
            mock_service.get_sessions = Mock(return_value=[{"id": "1"}, {"id": "2"}])

            stats = manager.get_statistics()
            assert first_service_name in stats["services"]


class TestServiceManagerIntegration:
    """Integration tests for ServiceManager."""

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary log directory."""
        return tmp_path / "logs"

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        with patch("honeypot.service_manager.load_config") as mock:
            config = Mock()
            config.ssh = Mock(enabled=True, host="127.0.0.1", port=12222)
            config.http = Mock(enabled=True, host="127.0.0.1", port=18080)
            config.telnet = Mock(enabled=False)
            config.ftp = Mock(enabled=False)
            mock.return_value = config
            yield config

    @pytest.mark.asyncio
    async def test_start_all_services(self, mock_config, log_dir):
        """Test starting all services."""
        with patch("honeypot.service_manager.SSHHoneypot") as mock_ssh, \
             patch("honeypot.service_manager.HTTPHoneypot") as mock_http:
            # Mock the start methods
            mock_ssh.return_value.start = AsyncMock()
            mock_http.return_value.start = AsyncMock()

            manager = ServiceManager(log_dir=log_dir)
            await manager.start_all()

            # Check that services were started
            assert manager.status["ssh"].running is True
            assert manager.status["http"].running is True

    @pytest.mark.asyncio
    async def test_stop_all_services(self, mock_config, log_dir):
        """Test stopping all services."""
        with patch("honeypot.service_manager.SSHHoneypot") as mock_ssh, \
             patch("honeypot.service_manager.HTTPHoneypot") as mock_http:
            # Mock the start and stop methods
            mock_ssh_instance = Mock()
            mock_ssh_instance.start = AsyncMock()
            mock_ssh_instance.stop = Mock()
            mock_ssh.return_value = mock_ssh_instance

            mock_http_instance = Mock()
            mock_http_instance.start = AsyncMock()
            mock_http_instance.stop = Mock()
            mock_http.return_value = mock_http_instance

            manager = ServiceManager(log_dir=log_dir)
            await manager.start_all()
            await manager.stop_all()

            # Check that services were stopped
            assert manager.status["ssh"].running is False
            assert manager.status["http"].running is False

    @pytest.mark.asyncio
    async def test_monitor_services(self, mock_config, log_dir):
        """Test service monitoring."""
        with patch("honeypot.service_manager.SSHHoneypot") as mock_ssh, \
             patch("honeypot.service_manager.HTTPHoneypot") as mock_http:
            # Mock services
            mock_ssh.return_value.start = AsyncMock()
            mock_http.return_value.start = AsyncMock()

            manager = ServiceManager(log_dir=log_dir)

            # Start monitoring with short interval
            monitor_task = asyncio.create_task(manager.monitor_services(interval=1))

            # Let it run for a short time
            await asyncio.sleep(0.1)

            # Stop monitoring
            manager.shutdown_requested = True
            await asyncio.sleep(1.2)  # Wait for one monitoring cycle

            # Cancel the task
            if not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
