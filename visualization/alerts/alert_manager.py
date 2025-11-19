"""
Alert manager for HP_TI platform.

Handles alert generation, routing, and notification delivery across
multiple channels (email, Slack, webhooks, etc.).
"""

import logging
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Alert:
    """
    Represents an alert event.
    """

    name: str
    severity: AlertSeverity
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "name": self.name,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolution_time": (
                self.resolution_time.isoformat() if self.resolution_time else None
            ),
        }

    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.resolved = True
        self.resolution_time = datetime.utcnow()


class AlertRule:
    """
    Defines an alert rule with conditions and actions.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        severity: AlertSeverity,
        message_template: str,
        cooldown_seconds: int = 300,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize alert rule.

        Args:
            name: Rule name
            condition: Function that returns True if alert should fire
            severity: Alert severity level
            message_template: Message template (supports {key} formatting)
            cooldown_seconds: Minimum seconds between alerts
            metadata: Additional metadata
        """
        self.name = name
        self.condition = condition
        self.severity = severity
        self.message_template = message_template
        self.cooldown_seconds = cooldown_seconds
        self.metadata = metadata or {}
        self.last_fired: Optional[datetime] = None

    def should_fire(self, data: Dict[str, Any]) -> bool:
        """
        Check if alert should fire.

        Args:
            data: Data to evaluate

        Returns:
            True if alert should fire
        """
        # Check cooldown
        if self.last_fired:
            cooldown_delta = timedelta(seconds=self.cooldown_seconds)
            if datetime.utcnow() - self.last_fired < cooldown_delta:
                return False

        # Evaluate condition
        return self.condition(data)

    def create_alert(self, data: Dict[str, Any]) -> Alert:
        """
        Create an alert from this rule.

        Args:
            data: Data for message formatting

        Returns:
            Alert instance
        """
        self.last_fired = datetime.utcnow()

        try:
            message = self.message_template.format(**data)
        except KeyError as e:
            logger.warning(f"Missing key in alert message template: {e}")
            message = self.message_template

        return Alert(
            name=self.name,
            severity=self.severity,
            message=message,
            source="alert_rule",
            metadata={**self.metadata, **data},
        )


class AlertChannel:
    """
    Base class for alert notification channels.
    """

    def __init__(self, name: str):
        """
        Initialize alert channel.

        Args:
            name: Channel name
        """
        self.name = name

    async def send(self, alert: Alert) -> bool:
        """
        Send alert notification.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully
        """
        raise NotImplementedError()


class LogChannel(AlertChannel):
    """
    Sends alerts to log file.
    """

    def __init__(self, name: str = "log", log_file: Optional[Path] = None):
        """
        Initialize log channel.

        Args:
            name: Channel name
            log_file: Path to log file (optional)
        """
        super().__init__(name)
        self.log_file = log_file
        self.logger = logging.getLogger(f"alerts.{name}")

    async def send(self, alert: Alert) -> bool:
        """Send alert to log."""
        try:
            log_message = (
                f"[{alert.severity.value.upper()}] {alert.name}: {alert.message}"
            )

            if alert.severity == AlertSeverity.CRITICAL:
                self.logger.critical(log_message, extra=alert.metadata)
            elif alert.severity == AlertSeverity.HIGH:
                self.logger.error(log_message, extra=alert.metadata)
            elif alert.severity == AlertSeverity.MEDIUM:
                self.logger.warning(log_message, extra=alert.metadata)
            else:
                self.logger.info(log_message, extra=alert.metadata)

            # Also write to file if specified
            if self.log_file:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(alert.to_dict()) + "\n")

            return True

        except Exception as e:
            logger.error(f"Failed to send alert to log: {e}")
            return False


class ConsoleChannel(AlertChannel):
    """
    Prints alerts to console (for development/testing).
    """

    def __init__(self, name: str = "console"):
        """Initialize console channel."""
        super().__init__(name)

    async def send(self, alert: Alert) -> bool:
        """Print alert to console."""
        try:
            severity_colors = {
                AlertSeverity.CRITICAL: "\033[91m",  # Red
                AlertSeverity.HIGH: "\033[93m",  # Yellow
                AlertSeverity.MEDIUM: "\033[94m",  # Blue
                AlertSeverity.LOW: "\033[92m",  # Green
                AlertSeverity.INFO: "\033[97m",  # White
            }
            reset_color = "\033[0m"

            color = severity_colors.get(alert.severity, "")
            print(
                f"{color}[ALERT] [{alert.severity.value.upper()}] "
                f"{alert.name}: {alert.message}{reset_color}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send alert to console: {e}")
            return False


class EmailChannel(AlertChannel):
    """
    Sends alerts via email.
    """

    def __init__(
        self,
        name: str = "email",
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        from_addr: str = "alerts@hp-ti.local",
        to_addrs: List[str] = None,
        use_tls: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize email channel.

        Args:
            name: Channel name
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            from_addr: From email address
            to_addrs: List of recipient email addresses
            use_tls: Use TLS encryption
            username: SMTP username (optional)
            password: SMTP password (optional)
        """
        super().__init__(name)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls
        self.username = username
        self.password = password

    async def send(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[HP_TI Alert] [{alert.severity.value.upper()}] {alert.name}"

            # Create body
            body = f"""
HP_TI Alert Notification

Severity: {alert.severity.value.upper()}
Alert: {alert.name}
Time: {alert.timestamp.isoformat()}
Source: {alert.source}

Message:
{alert.message}

Metadata:
{json.dumps(alert.metadata, indent=2)}
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)

                server.send_message(msg)

            logger.info(f"Alert sent via email to {self.to_addrs}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert via email: {e}")
            return False


class SlackChannel(AlertChannel):
    """
    Sends alerts to Slack via webhook.
    """

    def __init__(self, name: str = "slack", webhook_url: str = ""):
        """
        Initialize Slack channel.

        Args:
            name: Channel name
            webhook_url: Slack webhook URL
        """
        super().__init__(name)
        self.webhook_url = webhook_url

    async def send(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            import aiohttp

            # Choose color based on severity
            color_map = {
                AlertSeverity.CRITICAL: "#ff0000",  # Red
                AlertSeverity.HIGH: "#ff9900",  # Orange
                AlertSeverity.MEDIUM: "#ffcc00",  # Yellow
                AlertSeverity.LOW: "#3399ff",  # Blue
                AlertSeverity.INFO: "#999999",  # Gray
            }

            # Create Slack message payload
            payload = {
                "attachments": [
                    {
                        "fallback": f"[{alert.severity.value.upper()}] {alert.name}: {alert.message}",
                        "color": color_map.get(alert.severity, "#999999"),
                        "title": f"[{alert.severity.value.upper()}] {alert.name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Source",
                                "value": alert.source,
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.isoformat(),
                                "short": True,
                            },
                        ],
                        "footer": "HP_TI Alert System",
                        "ts": int(alert.timestamp.timestamp()),
                    }
                ]
            }

            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload
                ) as response:
                    if response.status == 200:
                        logger.info("Alert sent to Slack successfully")
                        return True
                    else:
                        logger.error(
                            f"Slack webhook returned status {response.status}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Failed to send alert to Slack: {e}")
            return False


class AlertManager:
    """
    Centralized alert management system.

    Manages alert rules, evaluates conditions, and routes alerts to
    appropriate notification channels.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize alert manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[str, AlertChannel] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history = self.config.get("max_history", 1000)

        # Add default log channel
        log_file = self.config.get("log_file")
        self.add_channel(LogChannel(log_file=Path(log_file) if log_file else None))

        logger.info("Alert manager initialized")

    def add_rule(self, rule: AlertRule) -> None:
        """
        Add an alert rule.

        Args:
            rule: Alert rule to add
        """
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def add_channel(self, channel: AlertChannel) -> None:
        """
        Add a notification channel.

        Args:
            channel: Alert channel to add
        """
        self.channels[channel.name] = channel
        logger.info(f"Added alert channel: {channel.name}")

    async def evaluate_rules(self, data: Dict[str, Any]) -> List[Alert]:
        """
        Evaluate all rules against provided data.

        Args:
            data: Data to evaluate

        Returns:
            List of alerts that fired
        """
        fired_alerts = []

        for rule in self.rules.values():
            try:
                if rule.should_fire(data):
                    alert = rule.create_alert(data)
                    fired_alerts.append(alert)
                    await self.fire_alert(alert)

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")

        return fired_alerts

    async def fire_alert(
        self, alert: Alert, channels: Optional[List[str]] = None
    ) -> None:
        """
        Fire an alert and send to channels.

        Args:
            alert: Alert to fire
            channels: List of channel names (None = all channels)
        """
        # Store alert
        self.active_alerts[alert.name] = alert
        self.alert_history.append(alert)

        # Trim history if needed
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history :]

        # Determine which channels to use
        target_channels = (
            channels if channels else list(self.channels.keys())
        )

        # Send to channels
        tasks = []
        for channel_name in target_channels:
            if channel_name in self.channels:
                channel = self.channels[channel_name]
                tasks.append(channel.send(alert))

        # Wait for all sends to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        success_count = sum(1 for r in results if r is True)
        logger.info(
            f"Alert '{alert.name}' sent to {success_count}/{len(tasks)} channels"
        )

    def resolve_alert(self, alert_name: str) -> Optional[Alert]:
        """
        Resolve an active alert.

        Args:
            alert_name: Name of alert to resolve

        Returns:
            Resolved alert or None
        """
        if alert_name in self.active_alerts:
            alert = self.active_alerts[alert_name]
            alert.resolve()
            del self.active_alerts[alert_name]
            logger.info(f"Alert resolved: {alert_name}")
            return alert

        return None

    def get_active_alerts(
        self, severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """
        Get active alerts.

        Args:
            severity: Filter by severity (optional)

        Returns:
            List of active alerts
        """
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_history(
        self, limit: int = 100, severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """
        Get alert history.

        Args:
            limit: Maximum number of alerts to return
            severity: Filter by severity (optional)

        Returns:
            List of historical alerts
        """
        alerts = self.alert_history

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(config: Optional[Dict[str, Any]] = None) -> AlertManager:
    """
    Get global alert manager instance.

    Args:
        config: Configuration dictionary (only used on first call)

    Returns:
        AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(config)
    return _alert_manager
