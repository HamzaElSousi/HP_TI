"""
Prometheus metrics exporter for HP_TI honeypot services.

Exposes metrics for monitoring honeypot activity, including connections,
authentication attempts, commands, and session statistics.
"""

import logging
from typing import Dict, Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    start_http_server,
    REGISTRY,
)

logger = logging.getLogger(__name__)


class HoneypotMetrics:
    """
    Centralized metrics collection for all honeypot services.

    Exposes Prometheus metrics for monitoring honeypot activity across
    SSH, HTTP, Telnet, and FTP services.
    """

    def __init__(self, namespace: str = "honeypot"):
        """
        Initialize honeypot metrics.

        Args:
            namespace: Prometheus namespace for metrics
        """
        self.namespace = namespace

        # Connection metrics
        self.connections_total = Counter(
            f"{namespace}_connections_total",
            "Total number of connections to honeypot services",
            ["service", "status"],  # status: accepted, rejected, failed
        )

        self.connections_active = Gauge(
            f"{namespace}_connections_active",
            "Number of currently active connections",
            ["service"],
        )

        self.connection_duration_seconds = Histogram(
            f"{namespace}_connection_duration_seconds",
            "Duration of honeypot connections in seconds",
            ["service"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
        )

        # Authentication metrics
        self.auth_attempts_total = Counter(
            f"{namespace}_auth_attempts_total",
            "Total number of authentication attempts",
            ["service", "success"],  # success: true, false
        )

        self.unique_credentials = Gauge(
            f"{namespace}_unique_credentials",
            "Number of unique credential pairs observed",
            ["service"],
        )

        self.unique_usernames = Gauge(
            f"{namespace}_unique_usernames",
            "Number of unique usernames observed",
            ["service"],
        )

        # Command metrics
        self.commands_total = Counter(
            f"{namespace}_commands_total",
            "Total number of commands executed",
            ["service", "command_type"],  # command_type: shell, upload, download, etc.
        )

        self.malicious_commands_total = Counter(
            f"{namespace}_malicious_commands_total",
            "Total number of detected malicious commands",
            ["service", "pattern"],  # pattern: botnet, scanner, exploit, etc.
        )

        # Attack metrics
        self.attacks_total = Counter(
            f"{namespace}_attacks_total",
            "Total number of detected attacks",
            ["service", "attack_type"],  # attack_type: sql_injection, xss, etc.
        )

        self.attack_sources = Gauge(
            f"{namespace}_attack_sources",
            "Number of unique attacking IP addresses",
            ["service"],
        )

        # Session metrics
        self.sessions_total = Counter(
            f"{namespace}_sessions_total",
            "Total number of sessions",
            ["service"],
        )

        self.sessions_active = Gauge(
            f"{namespace}_sessions_active",
            "Number of currently active sessions",
            ["service"],
        )

        # Data transfer metrics
        self.bytes_received_total = Counter(
            f"{namespace}_bytes_received_total",
            "Total bytes received from attackers",
            ["service"],
        )

        self.bytes_sent_total = Counter(
            f"{namespace}_bytes_sent_total",
            "Total bytes sent to attackers",
            ["service"],
        )

        # Service health metrics
        self.service_up = Gauge(
            f"{namespace}_service_up",
            "Service availability (1 = up, 0 = down)",
            ["service"],
        )

        self.service_errors_total = Counter(
            f"{namespace}_service_errors_total",
            "Total number of service errors",
            ["service", "error_type"],
        )

        # Geographic metrics
        self.connections_by_country = Counter(
            f"{namespace}_connections_by_country",
            "Connections grouped by country",
            ["service", "country_code"],
        )

        # HTTP-specific metrics
        self.http_requests_total = Counter(
            f"{namespace}_http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status_code"],
        )

        self.http_attack_vectors = Counter(
            f"{namespace}_http_attack_vectors",
            "HTTP attack attempts by vector",
            ["vector"],  # sql_injection, xss, path_traversal, etc.
        )

        # FTP-specific metrics
        self.ftp_operations_total = Counter(
            f"{namespace}_ftp_operations_total",
            "FTP operations attempted",
            ["operation"],  # RETR, STOR, LIST, etc.
        )

        # System info
        self.info = Info(
            f"{namespace}_info",
            "Honeypot system information",
        )

        # Initialize info
        self.info.info({
            "version": "1.0.0",
            "services": "ssh,http,telnet,ftp",
        })

        logger.info(f"Honeypot metrics initialized with namespace: {namespace}")

    def record_connection(
        self,
        service: str,
        status: str = "accepted",
        duration: Optional[float] = None,
        country_code: Optional[str] = None,
    ) -> None:
        """
        Record a connection event.

        Args:
            service: Service name (ssh, http, telnet, ftp)
            status: Connection status (accepted, rejected, failed)
            duration: Connection duration in seconds
            country_code: ISO country code of attacker
        """
        self.connections_total.labels(service=service, status=status).inc()

        if duration is not None:
            self.connection_duration_seconds.labels(service=service).observe(duration)

        if country_code:
            self.connections_by_country.labels(
                service=service, country_code=country_code
            ).inc()

    def record_auth_attempt(
        self,
        service: str,
        success: bool = False,
        username: Optional[str] = None,
    ) -> None:
        """
        Record an authentication attempt.

        Args:
            service: Service name
            success: Whether authentication succeeded
            username: Username used (for tracking unique usernames)
        """
        self.auth_attempts_total.labels(
            service=service, success=str(success).lower()
        ).inc()

    def record_command(
        self,
        service: str,
        command_type: str = "shell",
        is_malicious: bool = False,
        pattern: Optional[str] = None,
    ) -> None:
        """
        Record a command execution.

        Args:
            service: Service name
            command_type: Type of command (shell, upload, download, etc.)
            is_malicious: Whether command is identified as malicious
            pattern: Malicious pattern type if applicable
        """
        self.commands_total.labels(
            service=service, command_type=command_type
        ).inc()

        if is_malicious and pattern:
            self.malicious_commands_total.labels(
                service=service, pattern=pattern
            ).inc()

    def record_attack(self, service: str, attack_type: str) -> None:
        """
        Record a detected attack.

        Args:
            service: Service name
            attack_type: Type of attack detected
        """
        self.attacks_total.labels(service=service, attack_type=attack_type).inc()

    def record_session_start(self, service: str) -> None:
        """
        Record a new session start.

        Args:
            service: Service name
        """
        self.sessions_total.labels(service=service).inc()
        self.sessions_active.labels(service=service).inc()

    def record_session_end(self, service: str) -> None:
        """
        Record a session end.

        Args:
            service: Service name
        """
        self.sessions_active.labels(service=service).dec()

    def record_data_transfer(
        self, service: str, bytes_received: int = 0, bytes_sent: int = 0
    ) -> None:
        """
        Record data transfer.

        Args:
            service: Service name
            bytes_received: Bytes received from attacker
            bytes_sent: Bytes sent to attacker
        """
        if bytes_received > 0:
            self.bytes_received_total.labels(service=service).inc(bytes_received)

        if bytes_sent > 0:
            self.bytes_sent_total.labels(service=service).inc(bytes_sent)

    def set_service_status(self, service: str, is_up: bool) -> None:
        """
        Set service availability status.

        Args:
            service: Service name
            is_up: Whether service is up
        """
        self.service_up.labels(service=service).set(1 if is_up else 0)

    def record_service_error(self, service: str, error_type: str) -> None:
        """
        Record a service error.

        Args:
            service: Service name
            error_type: Type of error
        """
        self.service_errors_total.labels(
            service=service, error_type=error_type
        ).inc()

    def update_active_connections(self, service: str, count: int) -> None:
        """
        Update active connection count.

        Args:
            service: Service name
            count: Number of active connections
        """
        self.connections_active.labels(service=service).set(count)

    def update_unique_credentials(self, service: str, count: int) -> None:
        """
        Update unique credentials count.

        Args:
            service: Service name
            count: Number of unique credentials
        """
        self.unique_credentials.labels(service=service).set(count)

    def update_unique_usernames(self, service: str, count: int) -> None:
        """
        Update unique usernames count.

        Args:
            service: Service name
            count: Number of unique usernames
        """
        self.unique_usernames.labels(service=service).set(count)

    def update_attack_sources(self, service: str, count: int) -> None:
        """
        Update unique attack sources count.

        Args:
            service: Service name
            count: Number of unique attacking IPs
        """
        self.attack_sources.labels(service=service).set(count)

    # HTTP-specific methods
    def record_http_request(
        self, method: str, path: str, status_code: int
    ) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: HTTP status code
        """
        self.http_requests_total.labels(
            method=method, path=path, status_code=str(status_code)
        ).inc()

    def record_http_attack_vector(self, vector: str) -> None:
        """
        Record an HTTP attack vector.

        Args:
            vector: Attack vector type
        """
        self.http_attack_vectors.labels(vector=vector).inc()

    # FTP-specific methods
    def record_ftp_operation(self, operation: str) -> None:
        """
        Record an FTP operation.

        Args:
            operation: FTP command (RETR, STOR, LIST, etc.)
        """
        self.ftp_operations_total.labels(operation=operation).inc()

    def get_metrics_summary(self) -> Dict[str, any]:
        """
        Get a summary of current metrics.

        Returns:
            Dictionary with metric summaries
        """
        # This is a simplified summary; in production, you'd query Prometheus
        return {
            "connections": "See Prometheus for current values",
            "sessions": "See Prometheus for current values",
            "attacks": "See Prometheus for current values",
        }


# Global metrics instance
_metrics: Optional[HoneypotMetrics] = None


def get_metrics() -> HoneypotMetrics:
    """
    Get global metrics instance.

    Returns:
        HoneypotMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = HoneypotMetrics()
    return _metrics


def start_metrics_server(port: int = 9090) -> None:
    """
    Start Prometheus metrics HTTP server.

    Args:
        port: Port to listen on (default: 9090)
    """
    try:
        start_http_server(port)
        logger.info(f"Metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        raise
