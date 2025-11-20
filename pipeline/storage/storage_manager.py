"""
Storage manager for HP_TI.

Coordinates storage of honeypot data across multiple backends
(PostgreSQL and Elasticsearch).
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from pipeline.storage.postgres_client import PostgreSQLClient
from pipeline.storage.elasticsearch_client import ElasticsearchClient
from threat_intel.parsers.ssh_parser import SSHParser, SSHLogEntry

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages storage of honeypot data across multiple backends.

    Coordinates writing to PostgreSQL (structured data) and
    Elasticsearch (log search and analytics).
    """

    def __init__(
        self,
        postgres_client: PostgreSQLClient,
        elasticsearch_client: ElasticsearchClient,
    ):
        """
        Initialize storage manager.

        Args:
            postgres_client: PostgreSQL client instance
            elasticsearch_client: Elasticsearch client instance
        """
        self.postgres = postgres_client
        self.elasticsearch = elasticsearch_client
        self.ssh_parser = SSHParser()
        self.logger = logging.getLogger(__name__)

    def process_ssh_log_entries(self, log_lines: List[str]) -> Dict[str, int]:
        """
        Process SSH log entries and store them.

        Args:
            log_lines: List of raw log lines

        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "total": len(log_lines),
            "parsed": 0,
            "stored_postgres": 0,
            "stored_elasticsearch": 0,
            "errors": 0,
        }

        parsed_entries = []
        for line in log_lines:
            try:
                entry = self.ssh_parser.parse_line(line.strip())
                if entry:
                    parsed_entries.append(entry)
                    stats["parsed"] += 1
            except Exception as e:
                self.logger.warning(f"Error parsing log line: {e}")
                stats["errors"] += 1

        # Store in Elasticsearch (all entries for searchability)
        if parsed_entries:
            try:
                es_docs = [entry.raw_data for entry in parsed_entries]
                result = self.elasticsearch.bulk_index(es_docs, index_type="logs")
                stats["stored_elasticsearch"] = result["success"]
            except Exception as e:
                self.logger.error(f"Error storing to Elasticsearch: {e}")
                stats["errors"] += result.get("errors", 0)

        # Store in PostgreSQL (structured data only)
        for entry in parsed_entries:
            try:
                self._store_ssh_entry_postgres(entry)
                stats["stored_postgres"] += 1
            except Exception as e:
                self.logger.error(f"Error storing to PostgreSQL: {e}")
                stats["errors"] += 1

        self.logger.info(f"Processed {stats['parsed']}/{stats['total']} log entries")
        return stats

    def _store_ssh_entry_postgres(self, entry: SSHLogEntry) -> None:
        """
        Store SSH log entry in PostgreSQL based on event type.

        Args:
            entry: Parsed SSH log entry
        """
        category = self.ssh_parser.categorize_entry(entry)

        if category == "authentication":
            self._store_auth_attempt(entry)
        elif category == "command":
            self._store_command(entry)
        elif category == "session":
            self._store_session_event(entry)
        # System events don't need structured storage

    def _store_auth_attempt(self, entry: SSHLogEntry) -> None:
        """Store authentication attempt in PostgreSQL."""
        auth_data = self.ssh_parser.extract_auth_attempt(entry)
        if not auth_data or not auth_data.get("session_id"):
            return

        try:
            self.postgres.create_auth_attempt(
                session_id=auth_data["session_id"],
                username=auth_data.get("username", "unknown"),
                password=auth_data.get("password"),
                auth_method=auth_data.get("auth_method", "password"),
                success=auth_data.get("success", False),
            )
        except Exception as e:
            self.logger.error(f"Error storing auth attempt: {e}")

    def _store_command(self, entry: SSHLogEntry) -> None:
        """Store command execution in PostgreSQL."""
        cmd_data = self.ssh_parser.extract_command(entry)
        if not cmd_data or not cmd_data.get("session_id") or not cmd_data.get("command"):
            return

        try:
            self.postgres.create_command(
                session_id=cmd_data["session_id"],
                command=cmd_data["command"],
            )
        except Exception as e:
            self.logger.error(f"Error storing command: {e}")

    def _store_session_event(self, entry: SSHLogEntry) -> None:
        """Store session event in PostgreSQL."""
        session_data = self.ssh_parser.extract_session_event(entry)
        if not session_data:
            return

        event_type = session_data.get("event_type")

        try:
            if event_type == "connection_attempt":
                # Create new session
                self.postgres.create_session(
                    session_id=session_data["session_id"],
                    source_ip=session_data.get("source_ip", "0.0.0.0"),
                    source_port=session_data.get("source_port", 0),
                    honeypot_service="ssh",
                )
            elif event_type == "session_ended":
                # Update session with end time and final data
                session_metadata = session_data.get("session_data", {})
                updates = {
                    "end_time": session_data["timestamp"],
                    "session_data": session_metadata,
                }
                self.postgres.update_session(session_data["session_id"], updates)
        except Exception as e:
            self.logger.error(f"Error storing session event: {e}")

    def store_ip_intelligence(
        self, ip: str, intelligence_data: Dict[str, Any]
    ) -> None:
        """
        Store or update IP intelligence data.

        Args:
            ip: IP address
            intelligence_data: Intelligence data dictionary
        """
        try:
            self.postgres.upsert_ip_intelligence(ip, intelligence_data)
            self.logger.debug(f"Stored IP intelligence for {ip}")
        except Exception as e:
            self.logger.error(f"Error storing IP intelligence: {e}")

    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete session details from all sources.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session data or None
        """
        try:
            # Get from PostgreSQL
            session = self.postgres.get_session(session_id)
            if not session:
                return None

            # Get auth attempts
            with self.postgres.get_session() as db:
                auth_attempts = (
                    db.query(self.postgres.AuthAttempt)
                    .filter_by(session_id=session_id)
                    .all()
                )
                commands = (
                    db.query(self.postgres.Command)
                    .filter_by(session_id=session_id)
                    .all()
                )

            # Get from Elasticsearch
            es_logs = self.elasticsearch.search_by_session(session_id)

            return {
                "session": {
                    "id": str(session.id),
                    "source_ip": str(session.source_ip),
                    "source_port": session.source_port,
                    "service": session.honeypot_service,
                    "start_time": session.start_time.isoformat(),
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "command_count": session.command_count,
                    "auth_attempt_count": session.auth_attempt_count,
                },
                "auth_attempts": [
                    {
                        "username": a.username,
                        "password": a.password,
                        "method": a.auth_method,
                        "timestamp": a.timestamp.isoformat(),
                    }
                    for a in auth_attempts
                ],
                "commands": [
                    {
                        "command": c.command,
                        "response": c.response,
                        "timestamp": c.timestamp.isoformat(),
                    }
                    for c in commands
                ],
                "logs": es_logs,
            }
        except Exception as e:
            self.logger.error(f"Error getting session details: {e}")
            return None

    def get_attack_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get attack summary statistics.

        Args:
            start_time: Start of time period
            end_time: End of time period

        Returns:
            Dictionary with attack statistics
        """
        try:
            # Get stats from PostgreSQL
            pg_stats = self.postgres.get_attack_stats(start_time, end_time)

            # Get common credentials
            common_creds = self.postgres.get_common_credentials(limit=10)

            # Get common commands
            common_cmds = self.postgres.get_common_commands(limit=10)

            # Get document count from Elasticsearch
            es_count = self.elasticsearch.count(index_type="logs")

            return {
                "postgresql": pg_stats,
                "elasticsearch_documents": es_count,
                "top_credentials": [
                    {"username": u, "password": p, "count": c}
                    for u, p, c in common_creds
                ],
                "top_commands": [
                    {"command": cmd, "count": c} for cmd, c in common_cmds
                ],
            }
        except Exception as e:
            self.logger.error(f"Error getting attack summary: {e}")
            return {}

    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Clean up old data from storage backends.

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Dictionary with cleanup results
        """
        results = {}

        try:
            # Clean up Elasticsearch indices
            deleted_indices = self.elasticsearch.delete_old_indices(days_to_keep)
            results["elasticsearch_indices_deleted"] = deleted_indices
            self.logger.info(f"Deleted {len(deleted_indices)} old Elasticsearch indices")
        except Exception as e:
            self.logger.error(f"Error cleaning Elasticsearch: {e}")
            results["elasticsearch_error"] = str(e)

        # PostgreSQL cleanup would go here (implement based on retention policy)

        return results
