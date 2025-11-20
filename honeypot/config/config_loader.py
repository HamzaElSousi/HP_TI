"""
Configuration Loader for HP_TI

Handles loading and validation of configuration from environment variables
and YAML files using Pydantic for schema validation.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HoneypotSSHConfig(BaseSettings):
    """SSH Honeypot Configuration."""

    enabled: bool = Field(default=True, description="Enable SSH honeypot")
    host: str = Field(default="0.0.0.0", description="SSH honeypot bind address")
    port: int = Field(default=2222, description="SSH honeypot port")
    banner: str = Field(
        default="SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1",
        description="SSH banner string",
    )
    session_timeout: int = Field(default=300, description="Session timeout in seconds")
    max_connections_per_ip: int = Field(
        default=5, description="Maximum connections per IP"
    )

    model_config = SettingsConfigDict(
        env_prefix="HONEYPOT_SSH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class HoneypotHTTPConfig(BaseSettings):
    """HTTP Honeypot Configuration."""

    enabled: bool = Field(default=True, description="Enable HTTP honeypot")
    host: str = Field(default="0.0.0.0", description="HTTP honeypot bind address")
    port: int = Field(default=8080, description="HTTP honeypot port")
    https_port: int = Field(default=8443, description="HTTPS honeypot port")

    model_config = SettingsConfigDict(
        env_prefix="HONEYPOT_HTTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class HoneypotTelnetConfig(BaseSettings):
    """Telnet Honeypot Configuration."""

    enabled: bool = Field(default=False, description="Enable Telnet honeypot")
    host: str = Field(default="0.0.0.0", description="Telnet honeypot bind address")
    port: int = Field(default=2323, description="Telnet honeypot port")

    model_config = SettingsConfigDict(
        env_prefix="HONEYPOT_TELNET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class HoneypotFTPConfig(BaseSettings):
    """FTP Honeypot Configuration."""

    enabled: bool = Field(default=False, description="Enable FTP honeypot")
    host: str = Field(default="0.0.0.0", description="FTP honeypot bind address")
    port: int = Field(default=2121, description="FTP honeypot port")

    model_config = SettingsConfigDict(
        env_prefix="HONEYPOT_FTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DatabaseConfig(BaseSettings):
    """Database Configuration."""

    url: str = Field(
        default="postgresql://hp_ti_user:changeme@localhost:5432/hp_ti_db",
        description="Database URL",
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max pool overflow")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL database URL from DATABASE_URL env var."""
        return os.getenv("DATABASE_URL", self.url)


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch Configuration."""

    url: str = Field(
        default="http://localhost:9200", description="Elasticsearch URL"
    )
    username: Optional[str] = Field(default="elastic", description="Elasticsearch username")
    password: Optional[str] = Field(default=None, description="Elasticsearch password")
    index_prefix: str = Field(default="hp_ti", description="Index prefix")
    index_shards: int = Field(default=3, description="Number of shards")
    index_replicas: int = Field(default=1, description="Number of replicas")

    model_config = SettingsConfigDict(
        env_prefix="ELASTICSEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class RedisConfig(BaseSettings):
    """Redis Configuration."""

    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    cache_ttl: int = Field(default=86400, description="Default cache TTL in seconds")
    max_connections: int = Field(default=50, description="Max Redis connections")

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LoggingConfig(BaseSettings):
    """Logging Configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")
    dir: str = Field(default="./logs/honeypots", description="Log directory")

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppConfig(BaseSettings):
    """Main Application Configuration."""

    environment: str = Field(default="development", description="Environment name")
    app_name: str = Field(default="HP_TI", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class Config:
    """
    Centralized configuration management.

    Loads configuration from environment variables and optional YAML files.
    Uses Pydantic for validation and type safety.
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_file: Optional path to YAML configuration file
        """
        self.app = AppConfig()
        self.ssh = HoneypotSSHConfig()
        self.http = HoneypotHTTPConfig()
        self.telnet = HoneypotTelnetConfig()
        self.ftp = HoneypotFTPConfig()
        self.database = DatabaseConfig()
        self.elasticsearch = ElasticsearchConfig()
        self.redis = RedisConfig()
        self.logging = LoggingConfig()

        # Load from YAML if provided
        if config_file and config_file.exists():
            self._load_yaml(config_file)

    def _load_yaml(self, config_file: Path) -> None:
        """
        Load configuration from YAML file.

        Args:
            config_file: Path to YAML configuration file
        """
        with open(config_file, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        if not yaml_config:
            return

        # Update configurations from YAML
        for section, values in yaml_config.items():
            if hasattr(self, section) and isinstance(values, dict):
                config_obj = getattr(self, section)
                for key, value in values.items():
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        return {
            "app": self.app.model_dump(),
            "ssh": self.ssh.model_dump(),
            "http": self.http.model_dump(),
            "telnet": self.telnet.model_dump(),
            "ftp": self.ftp.model_dump(),
            "database": self.database.model_dump(),
            "elasticsearch": self.elasticsearch.model_dump(),
            "redis": self.redis.model_dump(),
            "logging": self.logging.model_dump(),
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config(config_file: Optional[Path] = None) -> Config:
    """
    Get global configuration instance.

    Args:
        config_file: Optional path to YAML configuration file

    Returns:
        Configuration instance
    """
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config


def reload_config(config_file: Optional[Path] = None) -> Config:
    """
    Reload configuration from scratch.

    Args:
        config_file: Optional path to YAML configuration file

    Returns:
        New configuration instance
    """
    global _config
    _config = Config(config_file)
    return _config


def load_config(config_file: Optional[Path] = None) -> Config:
    """
    Load configuration from file or environment.

    Alias for get_config() for compatibility with service_manager.

    Args:
        config_file: Optional path to YAML configuration file

    Returns:
        Configuration instance
    """
    return get_config(config_file)
