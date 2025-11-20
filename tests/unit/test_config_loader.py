"""
Unit tests for configuration loader.
"""

import pytest
from pathlib import Path
from honeypot.config.config_loader import (
    Config,
    HoneypotSSHConfig,
    DatabaseConfig,
    get_config,
    reload_config,
)


class TestHoneypotSSHConfig:
    """Tests for SSH honeypot configuration."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = HoneypotSSHConfig()

        assert config.enabled is True
        assert config.host == "0.0.0.0"
        assert config.port == 2222
        assert "SSH-2.0" in config.banner
        assert config.session_timeout == 300
        assert config.max_connections_per_ip == 5

    def test_custom_values(self):
        """Test that custom values override defaults."""
        config = HoneypotSSHConfig(
            enabled=False,
            port=2200,
            session_timeout=600,
        )

        assert config.enabled is False
        assert config.port == 2200
        assert config.session_timeout == 600


class TestDatabaseConfig:
    """Tests for database configuration."""

    def test_default_url(self):
        """Test default database URL."""
        config = DatabaseConfig()

        assert "postgresql://" in config.url
        assert config.pool_size == 10
        assert config.max_overflow == 20

    def test_postgres_url_property(self):
        """Test postgres_url property."""
        config = DatabaseConfig()
        url = config.postgres_url

        assert "postgresql://" in url


class TestConfig:
    """Tests for main configuration class."""

    def test_initialization(self):
        """Test configuration initialization."""
        config = Config()

        assert config.app is not None
        assert config.ssh is not None
        assert config.http is not None
        assert config.database is not None
        assert config.elasticsearch is not None
        assert config.redis is not None
        assert config.logging is not None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = Config()
        config_dict = config.to_dict()

        assert "app" in config_dict
        assert "ssh" in config_dict
        assert "database" in config_dict
        assert isinstance(config_dict["ssh"], dict)


class TestConfigSingleton:
    """Tests for configuration singleton pattern."""

    def test_get_config_returns_same_instance(self):
        """Test that get_config returns the same instance."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_reload_config_creates_new_instance(self):
        """Test that reload_config creates a new instance."""
        config1 = get_config()
        config2 = reload_config()

        assert config1 is not config2
