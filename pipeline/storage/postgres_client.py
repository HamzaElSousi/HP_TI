"""
PostgreSQL database client for HP_TI.

Manages database connections, sessions, and provides helper methods
for common database operations.
"""

import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from pipeline.storage.models import (
    Base,
    Session,
    AuthAttempt,
    Command,
    IPIntelligence,
    AttackPattern,
    Credential,
)

logger = logging.getLogger(__name__)


class PostgreSQLClient:
    """
    PostgreSQL database client with connection pooling and ORM support.

    Provides methods for storing and querying honeypot data.
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
    ):
        """
        Initialize PostgreSQL client.

        Args:
            database_url: Database connection URL
            pool_size: Connection pool size
            max_overflow: Max pool overflow connections
            pool_timeout: Pool timeout in seconds
        """
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        logger.info(f"PostgreSQL client initialized")

    def create_tables(self) -> None:
        """Create all database tables if they don't exist."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def drop_tables(self) -> None:
        """Drop all database tables. Use with caution!"""
        try:
            Base.metadata.drop_all(self.engine)
            logger.warning("All database tables dropped")
        except SQLAlchemyError as e:
            logger.error(f"Error dropping tables: {e}")
            raise

    @contextmanager
    def get_session(self):
        """
        Get a database session with automatic commit/rollback.

        Yields:
            Database session

        Example:
            >>> with client.get_session() as session:
            ...     session.add(new_record)
            ...     session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    # Session Methods

    def create_session(
        self,
        session_id: str,
        source_ip: str,
        source_port: int,
        honeypot_service: str,
        **kwargs,
    ) -> Session:
        """
        Create a new session record.

        Args:
            session_id: Unique session identifier
            source_ip: Source IP address
            source_port: Source port number
            honeypot_service: Honeypot service name
            **kwargs: Additional session data

        Returns:
            Created session object
        """
        with self.get_session() as db:
            session = Session(
                id=session_id,
                source_ip=source_ip,
                source_port=source_port,
                honeypot_service=honeypot_service,
                start_time=datetime.utcnow(),
                **kwargs,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.debug(f"Created session {session_id}")
            return session

    def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> Optional[Session]:
        """
        Update an existing session.

        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update

        Returns:
            Updated session or None if not found
        """
        with self.get_session() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                for key, value in updates.items():
                    setattr(session, key, value)
                session.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(session)
                logger.debug(f"Updated session {session_id}")
                return session
            return None

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        with self.get_session() as db:
            return db.query(Session).filter(Session.id == session_id).first()

    def get_sessions_by_ip(
        self, source_ip: str, limit: int = 100
    ) -> List[Session]:
        """
        Get all sessions from a specific IP.

        Args:
            source_ip: Source IP address
            limit: Maximum number of sessions to return

        Returns:
            List of session objects
        """
        with self.get_session() as db:
            return (
                db.query(Session)
                .filter(Session.source_ip == source_ip)
                .order_by(Session.start_time.desc())
                .limit(limit)
                .all()
            )

    # Auth Attempt Methods

    def create_auth_attempt(
        self,
        session_id: str,
        username: str,
        password: Optional[str] = None,
        auth_method: str = "password",
        **kwargs,
    ) -> AuthAttempt:
        """
        Create an authentication attempt record.

        Args:
            session_id: Associated session ID
            username: Attempted username
            password: Attempted password
            auth_method: Authentication method
            **kwargs: Additional auth attempt data

        Returns:
            Created auth attempt object
        """
        with self.get_session() as db:
            auth_attempt = AuthAttempt(
                session_id=session_id,
                username=username,
                password=password,
                auth_method=auth_method,
                timestamp=datetime.utcnow(),
                **kwargs,
            )
            db.add(auth_attempt)

            # Update session auth attempt count
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.auth_attempt_count += 1

            db.commit()
            db.refresh(auth_attempt)
            logger.debug(f"Created auth attempt for session {session_id}")
            return auth_attempt

    def get_common_credentials(self, limit: int = 100) -> List[tuple]:
        """
        Get most commonly used credential pairs.

        Args:
            limit: Maximum number of results

        Returns:
            List of (username, password, count) tuples
        """
        with self.get_session() as db:
            results = (
                db.query(
                    AuthAttempt.username,
                    AuthAttempt.password,
                    func.count(AuthAttempt.id).label("count"),
                )
                .group_by(AuthAttempt.username, AuthAttempt.password)
                .order_by(func.count(AuthAttempt.id).desc())
                .limit(limit)
                .all()
            )
            return [(r.username, r.password, r.count) for r in results]

    # Command Methods

    def create_command(
        self, session_id: str, command: str, response: Optional[str] = None
    ) -> Command:
        """
        Create a command execution record.

        Args:
            session_id: Associated session ID
            command: Command text
            response: Response provided by honeypot

        Returns:
            Created command object
        """
        with self.get_session() as db:
            cmd = Command(
                session_id=session_id,
                command=command,
                response=response,
                timestamp=datetime.utcnow(),
            )
            db.add(cmd)

            # Update session command count
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.command_count += 1

            db.commit()
            db.refresh(cmd)
            logger.debug(f"Created command for session {session_id}")
            return cmd

    def get_commands_by_session(self, session_id: str) -> List[Command]:
        """
        Get all commands for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of command objects
        """
        with self.get_session() as db:
            return (
                db.query(Command)
                .filter(Command.session_id == session_id)
                .order_by(Command.timestamp.asc())
                .all()
            )

    def get_common_commands(self, limit: int = 100) -> List[tuple]:
        """
        Get most commonly executed commands.

        Args:
            limit: Maximum number of results

        Returns:
            List of (command, count) tuples
        """
        with self.get_session() as db:
            results = (
                db.query(Command.command, func.count(Command.id).label("count"))
                .group_by(Command.command)
                .order_by(func.count(Command.id).desc())
                .limit(limit)
                .all()
            )
            return [(r.command, r.count) for r in results]

    # IP Intelligence Methods

    def upsert_ip_intelligence(self, ip: str, data: Dict[str, Any]) -> IPIntelligence:
        """
        Insert or update IP intelligence data.

        Args:
            ip: IP address
            data: Intelligence data dictionary

        Returns:
            IP intelligence object
        """
        with self.get_session() as db:
            ip_intel = db.query(IPIntelligence).filter(IPIntelligence.ip == ip).first()

            if ip_intel:
                # Update existing record
                for key, value in data.items():
                    if hasattr(ip_intel, key):
                        setattr(ip_intel, key, value)
                ip_intel.last_updated = datetime.utcnow()
                logger.debug(f"Updated IP intelligence for {ip}")
            else:
                # Create new record
                ip_intel = IPIntelligence(ip=ip, **data)
                db.add(ip_intel)
                logger.debug(f"Created IP intelligence for {ip}")

            db.commit()
            db.refresh(ip_intel)
            return ip_intel

    def get_ip_intelligence(self, ip: str) -> Optional[IPIntelligence]:
        """
        Get IP intelligence data.

        Args:
            ip: IP address

        Returns:
            IP intelligence object or None if not found
        """
        with self.get_session() as db:
            return db.query(IPIntelligence).filter(IPIntelligence.ip == ip).first()

    # Statistics and Analytics

    def get_attack_stats(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get attack statistics for a time period.

        Args:
            start_time: Start of time period
            end_time: End of time period

        Returns:
            Dictionary of statistics
        """
        with self.get_session() as db:
            query = db.query(Session)

            if start_time:
                query = query.filter(Session.start_time >= start_time)
            if end_time:
                query = query.filter(Session.start_time <= end_time)

            total_sessions = query.count()
            unique_ips = query.distinct(Session.source_ip).count()

            # Get service breakdown
            service_counts = (
                query.with_entities(
                    Session.honeypot_service, func.count(Session.id).label("count")
                )
                .group_by(Session.honeypot_service)
                .all()
            )

            return {
                "total_sessions": total_sessions,
                "unique_ips": unique_ips,
                "service_breakdown": {s: c for s, c in service_counts},
                "start_time": start_time,
                "end_time": end_time,
            }

    def close(self) -> None:
        """Close database engine and connections."""
        self.engine.dispose()
        logger.info("PostgreSQL client closed")
