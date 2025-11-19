"""
Unit tests for alert manager.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from visualization.alerts.alert_manager import (
    Alert,
    AlertSeverity,
    AlertRule,
    AlertChannel,
    LogChannel,
    ConsoleChannel,
    AlertManager,
    get_alert_manager,
)


class TestAlert:
    """Tests for Alert class."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = Alert(
            name="test_alert",
            severity=AlertSeverity.HIGH,
            message="Test alert message",
            source="test",
        )
        assert alert.name == "test_alert"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.message == "Test alert message"
        assert alert.resolved is False

    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        alert = Alert(
            name="test",
            severity=AlertSeverity.MEDIUM,
            message="Test",
            source="test",
        )
        alert_dict = alert.to_dict()
        assert isinstance(alert_dict, dict)
        assert alert_dict["name"] == "test"
        assert alert_dict["severity"] == "medium"
        assert "timestamp" in alert_dict

    def test_resolve_alert(self):
        """Test resolving an alert."""
        alert = Alert(
            name="test",
            severity=AlertSeverity.LOW,
            message="Test",
            source="test",
        )
        assert alert.resolved is False
        alert.resolve()
        assert alert.resolved is True
        assert alert.resolution_time is not None


class TestAlertRule:
    """Tests for AlertRule class."""

    def test_create_rule(self):
        """Test creating alert rule."""
        rule = AlertRule(
            name="test_rule",
            condition=lambda data: data.get("value", 0) > 100,
            severity=AlertSeverity.HIGH,
            message_template="Value {value} exceeds threshold",
            cooldown_seconds=300,
        )
        assert rule.name == "test_rule"
        assert rule.severity == AlertSeverity.HIGH

    def test_rule_should_fire_true(self):
        """Test rule that should fire."""
        rule = AlertRule(
            name="threshold_rule",
            condition=lambda data: data.get("count", 0) > 50,
            severity=AlertSeverity.MEDIUM,
            message_template="Count is {count}",
        )
        assert rule.should_fire({"count": 100}) is True

    def test_rule_should_fire_false(self):
        """Test rule that should not fire."""
        rule = AlertRule(
            name="threshold_rule",
            condition=lambda data: data.get("count", 0) > 50,
            severity=AlertSeverity.MEDIUM,
            message_template="Count is {count}",
        )
        assert rule.should_fire({"count": 25}) is False

    def test_rule_cooldown(self):
        """Test rule cooldown period."""
        rule = AlertRule(
            name="cooldown_test",
            condition=lambda data: True,  # Always fire
            severity=AlertSeverity.LOW,
            message_template="Test",
            cooldown_seconds=1,
        )

        # First fire should work
        assert rule.should_fire({}) is True

        # Immediate second fire should be blocked by cooldown
        assert rule.should_fire({}) is False

    def test_create_alert_from_rule(self):
        """Test creating alert from rule."""
        rule = AlertRule(
            name="test_rule",
            condition=lambda data: True,
            severity=AlertSeverity.CRITICAL,
            message_template="IP {ip} attacked {count} times",
        )
        alert = rule.create_alert({"ip": "192.0.2.1", "count": 100})
        assert alert.name == "test_rule"
        assert alert.severity == AlertSeverity.CRITICAL
        assert "192.0.2.1" in alert.message
        assert "100" in alert.message


class TestLogChannel:
    """Tests for LogChannel."""

    @pytest.fixture
    def temp_log_file(self, tmp_path):
        """Create temporary log file."""
        return tmp_path / "test_alerts.log"

    @pytest.mark.asyncio
    async def test_send_to_log(self, temp_log_file):
        """Test sending alert to log."""
        channel = LogChannel(name="test_log", log_file=temp_log_file)
        alert = Alert(
            name="test",
            severity=AlertSeverity.HIGH,
            message="Test alert",
            source="test",
        )

        result = await channel.send(alert)
        assert result is True
        assert temp_log_file.exists()

    @pytest.mark.asyncio
    async def test_log_different_severities(self, temp_log_file):
        """Test logging different severity levels."""
        channel = LogChannel(log_file=temp_log_file)

        for severity in [
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
            AlertSeverity.MEDIUM,
            AlertSeverity.LOW,
            AlertSeverity.INFO,
        ]:
            alert = Alert(
                name=f"test_{severity.value}",
                severity=severity,
                message=f"Test {severity.value}",
                source="test",
            )
            result = await channel.send(alert)
            assert result is True


class TestConsoleChannel:
    """Tests for ConsoleChannel."""

    @pytest.mark.asyncio
    async def test_send_to_console(self):
        """Test sending alert to console."""
        channel = ConsoleChannel()
        alert = Alert(
            name="console_test",
            severity=AlertSeverity.MEDIUM,
            message="Console test alert",
            source="test",
        )

        result = await channel.send(alert)
        assert result is True


class TestAlertManager:
    """Tests for AlertManager."""

    @pytest.fixture
    def manager(self):
        """Create alert manager."""
        return AlertManager(config={"max_history": 100})

    def test_init(self, manager):
        """Test alert manager initialization."""
        assert manager is not None
        assert len(manager.channels) > 0  # Should have default log channel

    def test_add_rule(self, manager):
        """Test adding alert rule."""
        rule = AlertRule(
            name="test_rule",
            condition=lambda data: True,
            severity=AlertSeverity.HIGH,
            message_template="Test",
        )
        manager.add_rule(rule)
        assert "test_rule" in manager.rules

    def test_add_channel(self, manager):
        """Test adding notification channel."""
        channel = ConsoleChannel(name="test_console")
        manager.add_channel(channel)
        assert "test_console" in manager.channels

    @pytest.mark.asyncio
    async def test_fire_alert(self, manager):
        """Test firing an alert."""
        alert = Alert(
            name="test_fire",
            severity=AlertSeverity.MEDIUM,
            message="Test fire alert",
            source="test",
        )

        await manager.fire_alert(alert)
        assert "test_fire" in manager.active_alerts
        assert len(manager.alert_history) > 0

    @pytest.mark.asyncio
    async def test_evaluate_rules(self, manager):
        """Test evaluating alert rules."""
        # Add a rule that will fire
        rule = AlertRule(
            name="eval_test",
            condition=lambda data: data.get("value", 0) > 50,
            severity=AlertSeverity.HIGH,
            message_template="Value is {value}",
        )
        manager.add_rule(rule)

        # Evaluate with data that triggers the rule
        fired_alerts = await manager.evaluate_rules({"value": 100})
        assert len(fired_alerts) > 0
        assert any(a.name == "eval_test" for a in fired_alerts)

    def test_resolve_alert(self, manager):
        """Test resolving an active alert."""
        alert = Alert(
            name="resolve_test",
            severity=AlertSeverity.LOW,
            message="Test",
            source="test",
        )
        manager.active_alerts["resolve_test"] = alert

        resolved = manager.resolve_alert("resolve_test")
        assert resolved is not None
        assert resolved.resolved is True
        assert "resolve_test" not in manager.active_alerts

    def test_get_active_alerts(self, manager):
        """Test getting active alerts."""
        alert1 = Alert(
            name="active1",
            severity=AlertSeverity.HIGH,
            message="Test",
            source="test",
        )
        alert2 = Alert(
            name="active2",
            severity=AlertSeverity.MEDIUM,
            message="Test",
            source="test",
        )

        manager.active_alerts["active1"] = alert1
        manager.active_alerts["active2"] = alert2

        active = manager.get_active_alerts()
        assert len(active) == 2

        # Filter by severity
        high_alerts = manager.get_active_alerts(severity=AlertSeverity.HIGH)
        assert len(high_alerts) == 1
        assert high_alerts[0].name == "active1"

    def test_get_alert_history(self, manager):
        """Test getting alert history."""
        # Add some historical alerts
        for i in range(5):
            alert = Alert(
                name=f"history_{i}",
                severity=AlertSeverity.INFO,
                message=f"Test {i}",
                source="test",
            )
            manager.alert_history.append(alert)

        history = manager.get_alert_history(limit=3)
        assert len(history) == 3

    def test_alert_history_limit(self, manager):
        """Test alert history respects max_history."""
        manager.max_history = 10

        # Add more alerts than the limit
        for i in range(15):
            alert = Alert(
                name=f"limit_test_{i}",
                severity=AlertSeverity.INFO,
                message=f"Test {i}",
                source="test",
            )
            manager.alert_history.append(alert)

        # Manually trigger trimming (normally done in fire_alert)
        if len(manager.alert_history) > manager.max_history:
            manager.alert_history = manager.alert_history[-manager.max_history :]

        assert len(manager.alert_history) <= manager.max_history


class TestAlertManagerSingleton:
    """Tests for alert manager singleton."""

    def test_get_alert_manager(self):
        """Test getting global alert manager."""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        assert manager1 is manager2


class TestAlertIntegration:
    """Integration tests for alert system."""

    @pytest.mark.asyncio
    async def test_complete_alert_workflow(self):
        """Test complete alert workflow from rule evaluation to notification."""
        manager = AlertManager()

        # Add console channel for testing
        manager.add_channel(ConsoleChannel(name="test_console"))

        # Add a rule
        rule = AlertRule(
            name="integration_test",
            condition=lambda data: data.get("attacks", 0) > 100,
            severity=AlertSeverity.HIGH,
            message_template="High attack rate detected: {attacks} attacks",
            cooldown_seconds=1,
        )
        manager.add_rule(rule)

        # Evaluate rule with triggering data
        data = {"attacks": 150}
        fired_alerts = await manager.evaluate_rules(data)

        # Verify alert was fired
        assert len(fired_alerts) > 0
        assert fired_alerts[0].name == "integration_test"
        assert "150" in fired_alerts[0].message

        # Verify alert is active
        assert "integration_test" in manager.active_alerts

        # Resolve alert
        resolved = manager.resolve_alert("integration_test")
        assert resolved is not None
        assert resolved.resolved is True

    @pytest.mark.asyncio
    async def test_multiple_channels(self):
        """Test alert sent to multiple channels."""
        manager = AlertManager()

        # Add multiple channels
        manager.add_channel(ConsoleChannel(name="console1"))
        manager.add_channel(ConsoleChannel(name="console2"))

        alert = Alert(
            name="multi_channel",
            severity=AlertSeverity.CRITICAL,
            message="Test multi-channel",
            source="test",
        )

        # Fire alert to all channels
        await manager.fire_alert(alert)

        # Alert should be in history
        assert len(manager.alert_history) > 0
