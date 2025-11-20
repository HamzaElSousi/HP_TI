"""
Database models for HP_TI using SQLAlchemy ORM.

These models define the PostgreSQL database schema for storing
structured threat intelligence data.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Session(Base):
    """
    Represents an attacker session.

    A session is created when an attacker connects to any honeypot service
    and ends when the connection is closed.
    """

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_ip = Column(INET, nullable=False, index=True)
    source_port = Column(Integer)
    honeypot_service = Column(String(50), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    end_time = Column(DateTime)
    command_count = Column(Integer, default=0)
    auth_attempt_count = Column(Integer, default=0)
    session_data = Column(JSON)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    auth_attempts = relationship(
        "AuthAttempt", back_populates="session", cascade="all, delete-orphan"
    )
    commands = relationship(
        "Command", back_populates="session", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_session_ip_time", "source_ip", "start_time"),
        Index("idx_session_service_time", "honeypot_service", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} from {self.source_ip} on {self.honeypot_service}>"


class AuthAttempt(Base):
    """
    Represents an authentication attempt by an attacker.

    Stores credentials and authentication methods used during attacks.
    """

    __tablename__ = "auth_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    username = Column(String(255), index=True)
    password = Column(String(255))
    auth_method = Column(String(50))  # password, publickey, etc.
    key_type = Column(String(50))  # For public key auth
    key_fingerprint = Column(String(255))
    success = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="auth_attempts")

    # Indexes
    __table_args__ = (
        Index("idx_auth_username_password", "username", "password"),
        Index("idx_auth_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuthAttempt {self.username}:{self.password[:10] if self.password else 'N/A'}>"


class Command(Base):
    """
    Represents a command executed by an attacker.

    Stores the command text and any response provided by the honeypot.
    """

    __tablename__ = "commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    command = Column(Text, nullable=False)
    response = Column(Text)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="commands")

    # Indexes
    __table_args__ = (Index("idx_command_timestamp", "timestamp"),)

    def __repr__(self) -> str:
        cmd_preview = self.command[:50] + "..." if len(self.command) > 50 else self.command
        return f"<Command '{cmd_preview}'>"


class IPIntelligence(Base):
    """
    Stores enriched intelligence data about IP addresses.

    This table is populated by the enrichment engine with data from
    external threat intelligence sources.
    """

    __tablename__ = "ip_intelligence"

    ip = Column(INET, primary_key=True)
    country_code = Column(String(2))
    country_name = Column(String(255))
    city = Column(String(255))
    latitude = Column(String(50))
    longitude = Column(String(50))
    asn = Column(Integer)
    asn_org = Column(String(255))
    isp = Column(String(255))
    is_vpn = Column(Boolean)
    is_tor = Column(Boolean)
    is_proxy = Column(Boolean)
    abuse_confidence_score = Column(Integer)  # 0-100 from AbuseIPDB
    total_reports = Column(Integer)
    last_reported_at = Column(DateTime)
    threat_level = Column(String(20))  # low, medium, high, critical
    enrichment_data = Column(JSON)  # Additional data from various sources
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_ip_country", "country_code"),
        Index("idx_ip_abuse_score", "abuse_confidence_score"),
        Index("idx_ip_threat_level", "threat_level"),
    )

    def __repr__(self) -> str:
        return f"<IPIntelligence {self.ip} ({self.country_code})>"


class AttackPattern(Base):
    """
    Stores detected attack patterns and campaigns.

    Represents coordinated attacks or recurring patterns identified
    by the correlation engine.
    """

    __tablename__ = "attack_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pattern_type = Column(String(100), nullable=False)  # brute_force, distributed, etc.
    pattern_name = Column(String(255))
    description = Column(Text)
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    occurrence_count = Column(Integer, default=1)
    source_ips = Column(JSON)  # List of involved IPs
    target_services = Column(JSON)  # List of targeted services
    credentials_used = Column(JSON)  # Common credentials
    severity = Column(String(20))  # low, medium, high, critical
    pattern_data = Column(JSON)  # Additional pattern metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_pattern_type_severity", "pattern_type", "severity"),
        Index("idx_pattern_last_seen", "last_seen"),
    )

    def __repr__(self) -> str:
        return f"<AttackPattern {self.pattern_type}: {self.pattern_name}>"


class Credential(Base):
    """
    Tracks unique credential pairs and their usage statistics.

    Useful for identifying common credential combinations and
    credential stuffing attacks.
    """

    __tablename__ = "credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(255), nullable=False, index=True)
    password = Column(String(255), nullable=False)
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    attempt_count = Column(Integer, default=1)
    unique_ips = Column(Integer, default=1)  # Count of unique IPs using this combo
    services_targeted = Column(JSON)  # List of services where this was used
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_credential_pair", "username", "password", unique=True),
        Index("idx_credential_count", "attempt_count"),
    )

    def __repr__(self) -> str:
        return f"<Credential {self.username}:*** ({self.attempt_count} attempts)>"


# Helper function to create all tables
def create_tables(engine):
    """
    Create all database tables.

    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.create_all(engine)


# Helper function to drop all tables (use with caution!)
def drop_tables(engine):
    """
    Drop all database tables.

    Args:
        engine: SQLAlchemy engine instance

    Warning:
        This will delete all data!
    """
    Base.metadata.drop_all(engine)
