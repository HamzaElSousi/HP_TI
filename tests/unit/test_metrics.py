"""
Unit tests for Prometheus metrics exporters.
"""

import pytest
from honeypot.metrics.prometheus_exporter import HoneypotMetrics, get_metrics
from pipeline.metrics.pipeline_metrics import PipelineMetrics, get_pipeline_metrics


class TestHoneypotMetrics:
    """Tests for honeypot metrics."""

    @pytest.fixture
    def metrics(self):
        """Create honeypot metrics instance."""
        return HoneypotMetrics(namespace="test_honeypot")

    def test_init(self, metrics):
        """Test metrics initialization."""
        assert metrics is not None
        assert metrics.namespace == "test_honeypot"

    def test_record_connection(self, metrics):
        """Test recording a connection."""
        # Should not raise exception
        metrics.record_connection("ssh", "accepted", duration=10.5, country_code="US")

    def test_record_auth_attempt(self, metrics):
        """Test recording authentication attempt."""
        metrics.record_auth_attempt("ssh", success=False, username="admin")

    def test_record_command(self, metrics):
        """Test recording command execution."""
        metrics.record_command("ssh", "shell", is_malicious=True, pattern="botnet")

    def test_record_attack(self, metrics):
        """Test recording attack."""
        metrics.record_attack("http", "sql_injection")

    def test_record_session_lifecycle(self, metrics):
        """Test session start and end."""
        metrics.record_session_start("ssh")
        metrics.record_session_end("ssh")

    def test_record_data_transfer(self, metrics):
        """Test data transfer recording."""
        metrics.record_data_transfer("ftp", bytes_received=1024, bytes_sent=512)

    def test_set_service_status(self, metrics):
        """Test setting service status."""
        metrics.set_service_status("ssh", is_up=True)
        metrics.set_service_status("http", is_up=False)

    def test_record_service_error(self, metrics):
        """Test recording service error."""
        metrics.record_service_error("ssh", "connection_timeout")

    def test_update_gauges(self, metrics):
        """Test updating gauge metrics."""
        metrics.update_active_connections("ssh", 5)
        metrics.update_unique_credentials("ssh", 100)
        metrics.update_unique_usernames("http", 50)
        metrics.update_attack_sources("telnet", 25)

    def test_http_specific_metrics(self, metrics):
        """Test HTTP-specific metrics."""
        metrics.record_http_request("GET", "/admin", 200)
        metrics.record_http_attack_vector("sql_injection")

    def test_ftp_specific_metrics(self, metrics):
        """Test FTP-specific metrics."""
        metrics.record_ftp_operation("RETR")
        metrics.record_ftp_operation("STOR")

    def test_get_metrics_summary(self, metrics):
        """Test getting metrics summary."""
        summary = metrics.get_metrics_summary()
        assert isinstance(summary, dict)
        assert "connections" in summary


class TestPipelineMetrics:
    """Tests for pipeline metrics."""

    @pytest.fixture
    def metrics(self):
        """Create pipeline metrics instance."""
        return PipelineMetrics(namespace="test_pipeline")

    def test_init(self, metrics):
        """Test pipeline metrics initialization."""
        assert metrics is not None
        assert metrics.namespace == "test_pipeline"

    def test_record_event_processed(self, metrics):
        """Test recording processed event."""
        metrics.record_event_processed("ingestion", "ssh", duration=0.05)

    def test_record_event_failed(self, metrics):
        """Test recording failed event."""
        metrics.record_event_failed("parsing", "invalid_format")

    def test_record_event_dropped(self, metrics):
        """Test recording dropped event."""
        metrics.record_event_dropped("enrichment", "rate_limit")

    def test_record_batch_processing(self, metrics):
        """Test recording batch processing."""
        metrics.record_batch_processing("storage", duration=2.5, count=100)

    def test_queue_operations(self, metrics):
        """Test queue metrics."""
        metrics.update_queue_size("events", 150)
        metrics.record_queue_item_added("events")
        metrics.record_queue_item_processed("events")

    def test_storage_operations(self, metrics):
        """Test storage metrics."""
        metrics.record_storage_write("postgres", "insert", duration=0.01)
        metrics.record_storage_error("elasticsearch", "connection_timeout")
        metrics.update_connection_pool("postgres", active=8, idle=2)

    def test_enrichment_operations(self, metrics):
        """Test enrichment metrics."""
        metrics.record_enrichment_call("geoip", "success", duration=0.1, confidence=95.0)
        metrics.record_cache_hit("abuseipdb")
        metrics.record_cache_miss("geoip")

    def test_parser_operations(self, metrics):
        """Test parser metrics."""
        metrics.record_log_parsed("ssh", success=True)
        metrics.record_parse_error("http", "malformed_json")

    def test_worker_operations(self, metrics):
        """Test worker metrics."""
        metrics.update_workers_active("enrichment", 4)
        metrics.record_worker_task("enrichment", "success")

    def test_correlation_operations(self, metrics):
        """Test correlation metrics."""
        metrics.record_pattern_detected("brute_force")
        metrics.record_correlation_operation("ip_aggregation")


class TestMetricsSingletons:
    """Tests for metrics singleton instances."""

    def test_get_honeypot_metrics(self):
        """Test getting global honeypot metrics instance."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2

    def test_get_pipeline_metrics(self):
        """Test getting global pipeline metrics instance."""
        metrics1 = get_pipeline_metrics()
        metrics2 = get_pipeline_metrics()
        assert metrics1 is metrics2


class TestMetricsIntegration:
    """Integration tests for metrics."""

    def test_metrics_export_format(self):
        """Test that metrics can be exported in Prometheus format."""
        metrics = HoneypotMetrics(namespace="integration_test")

        # Record some metrics
        metrics.record_connection("ssh", "accepted")
        metrics.record_auth_attempt("ssh", success=False)
        metrics.record_attack("http", "xss")

        # Metrics should be registered in Prometheus registry
        # In a real test, we'd scrape the /metrics endpoint
        assert metrics.connections_total is not None
        assert metrics.auth_attempts_total is not None
        assert metrics.attacks_total is not None

    def test_pipeline_metrics_workflow(self):
        """Test complete pipeline metrics workflow."""
        metrics = PipelineMetrics(namespace="workflow_test")

        # Simulate event processing pipeline
        metrics.record_event_processed("ingestion", "ssh", duration=0.01)
        metrics.record_event_processed("parsing", "ssh", duration=0.02)
        metrics.record_enrichment_call("geoip", "success", duration=0.05)
        metrics.record_storage_write("postgres", "insert", duration=0.01)

        # All metrics should be recorded without error
        assert True  # If we get here, workflow succeeded
