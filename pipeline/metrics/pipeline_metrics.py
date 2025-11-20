"""
Prometheus metrics for HP_TI data pipeline.

Tracks performance and health metrics for data ingestion, processing,
enrichment, and storage operations.
"""

import logging
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)


class PipelineMetrics:
    """
    Metrics collection for data pipeline operations.

    Tracks events processed, failures, latency, and queue sizes across
    the entire data processing pipeline.
    """

    def __init__(self, namespace: str = "pipeline"):
        """
        Initialize pipeline metrics.

        Args:
            namespace: Prometheus namespace for metrics
        """
        self.namespace = namespace

        # Event processing metrics
        self.events_processed_total = Counter(
            f"{namespace}_events_processed_total",
            "Total number of events processed",
            ["stage", "source"],  # stage: ingestion, parsing, enrichment, storage
        )

        self.events_failed_total = Counter(
            f"{namespace}_events_failed_total",
            "Total number of failed events",
            ["stage", "error_type"],
        )

        self.events_dropped_total = Counter(
            f"{namespace}_events_dropped_total",
            "Total number of dropped events",
            ["stage", "reason"],
        )

        # Processing duration metrics
        self.processing_duration_seconds = Histogram(
            f"{namespace}_processing_duration_seconds",
            "Event processing duration in seconds",
            ["stage"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
        )

        self.batch_processing_duration_seconds = Histogram(
            f"{namespace}_batch_processing_duration_seconds",
            "Batch processing duration in seconds",
            ["stage"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
        )

        # Queue metrics
        self.queue_size = Gauge(
            f"{namespace}_queue_size",
            "Current queue size",
            ["queue_name"],
        )

        self.queue_items_added_total = Counter(
            f"{namespace}_queue_items_added_total",
            "Total items added to queue",
            ["queue_name"],
        )

        self.queue_items_processed_total = Counter(
            f"{namespace}_queue_items_processed_total",
            "Total items processed from queue",
            ["queue_name"],
        )

        # Storage metrics
        self.storage_writes_total = Counter(
            f"{namespace}_storage_writes_total",
            "Total writes to storage backend",
            ["backend", "operation"],  # backend: postgres, elasticsearch
        )

        self.storage_write_errors_total = Counter(
            f"{namespace}_storage_write_errors_total",
            "Total storage write errors",
            ["backend", "error_type"],
        )

        self.storage_write_duration_seconds = Histogram(
            f"{namespace}_storage_write_duration_seconds",
            "Storage write duration in seconds",
            ["backend"],
            buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        )

        self.storage_connection_pool_size = Gauge(
            f"{namespace}_storage_connection_pool_size",
            "Database connection pool size",
            ["backend", "state"],  # state: active, idle
        )

        # Enrichment metrics
        self.enrichment_api_calls_total = Counter(
            f"{namespace}_enrichment_api_calls_total",
            "Total API calls for enrichment",
            ["provider", "status"],  # status: success, failure, cached
        )

        self.enrichment_cache_hits_total = Counter(
            f"{namespace}_enrichment_cache_hits_total",
            "Total enrichment cache hits",
            ["enricher"],
        )

        self.enrichment_cache_misses_total = Counter(
            f"{namespace}_enrichment_cache_misses_total",
            "Total enrichment cache misses",
            ["enricher"],
        )

        self.enrichment_duration_seconds = Histogram(
            f"{namespace}_enrichment_duration_seconds",
            "Enrichment duration in seconds",
            ["provider"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
        )

        self.enrichment_confidence_score = Summary(
            f"{namespace}_enrichment_confidence_score",
            "Enrichment confidence scores",
            ["provider"],
        )

        # Parser metrics
        self.log_lines_parsed_total = Counter(
            f"{namespace}_log_lines_parsed_total",
            "Total log lines parsed",
            ["parser", "success"],
        )

        self.parse_errors_total = Counter(
            f"{namespace}_parse_errors_total",
            "Total parsing errors",
            ["parser", "error_type"],
        )

        # Worker metrics
        self.workers_active = Gauge(
            f"{namespace}_workers_active",
            "Number of active worker processes/threads",
            ["worker_type"],
        )

        self.worker_tasks_total = Counter(
            f"{namespace}_worker_tasks_total",
            "Total tasks processed by workers",
            ["worker_type", "status"],  # status: success, failure
        )

        # Correlation metrics
        self.patterns_detected_total = Counter(
            f"{namespace}_patterns_detected_total",
            "Total attack patterns detected",
            ["pattern_type"],
        )

        self.correlation_operations_total = Counter(
            f"{namespace}_correlation_operations_total",
            "Total correlation operations",
            ["operation_type"],
        )

        logger.info(f"Pipeline metrics initialized with namespace: {namespace}")

    # Event processing methods
    def record_event_processed(
        self, stage: str, source: str, duration: Optional[float] = None
    ) -> None:
        """
        Record a successfully processed event.

        Args:
            stage: Pipeline stage (ingestion, parsing, enrichment, storage)
            source: Event source (ssh, http, telnet, ftp)
            duration: Processing duration in seconds
        """
        self.events_processed_total.labels(stage=stage, source=source).inc()

        if duration is not None:
            self.processing_duration_seconds.labels(stage=stage).observe(duration)

    def record_event_failed(self, stage: str, error_type: str) -> None:
        """
        Record a failed event.

        Args:
            stage: Pipeline stage
            error_type: Type of error
        """
        self.events_failed_total.labels(stage=stage, error_type=error_type).inc()

    def record_event_dropped(self, stage: str, reason: str) -> None:
        """
        Record a dropped event.

        Args:
            stage: Pipeline stage
            reason: Reason for dropping
        """
        self.events_dropped_total.labels(stage=stage, reason=reason).inc()

    def record_batch_processing(self, stage: str, duration: float, count: int) -> None:
        """
        Record batch processing operation.

        Args:
            stage: Pipeline stage
            duration: Processing duration in seconds
            count: Number of items in batch
        """
        self.batch_processing_duration_seconds.labels(stage=stage).observe(duration)

    # Queue methods
    def update_queue_size(self, queue_name: str, size: int) -> None:
        """
        Update queue size.

        Args:
            queue_name: Name of the queue
            size: Current queue size
        """
        self.queue_size.labels(queue_name=queue_name).set(size)

    def record_queue_item_added(self, queue_name: str) -> None:
        """
        Record item added to queue.

        Args:
            queue_name: Name of the queue
        """
        self.queue_items_added_total.labels(queue_name=queue_name).inc()

    def record_queue_item_processed(self, queue_name: str) -> None:
        """
        Record item processed from queue.

        Args:
            queue_name: Name of the queue
        """
        self.queue_items_processed_total.labels(queue_name=queue_name).inc()

    # Storage methods
    def record_storage_write(
        self,
        backend: str,
        operation: str = "insert",
        duration: Optional[float] = None,
    ) -> None:
        """
        Record a storage write operation.

        Args:
            backend: Storage backend (postgres, elasticsearch)
            operation: Type of operation (insert, update, delete)
            duration: Operation duration in seconds
        """
        self.storage_writes_total.labels(backend=backend, operation=operation).inc()

        if duration is not None:
            self.storage_write_duration_seconds.labels(backend=backend).observe(
                duration
            )

    def record_storage_error(self, backend: str, error_type: str) -> None:
        """
        Record a storage error.

        Args:
            backend: Storage backend
            error_type: Type of error
        """
        self.storage_write_errors_total.labels(
            backend=backend, error_type=error_type
        ).inc()

    def update_connection_pool(
        self, backend: str, active: int, idle: int
    ) -> None:
        """
        Update connection pool size.

        Args:
            backend: Storage backend
            active: Number of active connections
            idle: Number of idle connections
        """
        self.storage_connection_pool_size.labels(
            backend=backend, state="active"
        ).set(active)
        self.storage_connection_pool_size.labels(
            backend=backend, state="idle"
        ).set(idle)

    # Enrichment methods
    def record_enrichment_call(
        self,
        provider: str,
        status: str,
        duration: Optional[float] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """
        Record an enrichment API call.

        Args:
            provider: Enrichment provider (geoip, abuseipdb, whois, etc.)
            status: Call status (success, failure, cached)
            duration: Call duration in seconds
            confidence: Confidence score (0-100)
        """
        self.enrichment_api_calls_total.labels(
            provider=provider, status=status
        ).inc()

        if duration is not None:
            self.enrichment_duration_seconds.labels(provider=provider).observe(
                duration
            )

        if confidence is not None:
            self.enrichment_confidence_score.labels(provider=provider).observe(
                confidence
            )

    def record_cache_hit(self, enricher: str) -> None:
        """
        Record an enrichment cache hit.

        Args:
            enricher: Enricher name
        """
        self.enrichment_cache_hits_total.labels(enricher=enricher).inc()

    def record_cache_miss(self, enricher: str) -> None:
        """
        Record an enrichment cache miss.

        Args:
            enricher: Enricher name
        """
        self.enrichment_cache_misses_total.labels(enricher=enricher).inc()

    # Parser methods
    def record_log_parsed(self, parser: str, success: bool = True) -> None:
        """
        Record a log parsing operation.

        Args:
            parser: Parser name (ssh, http, telnet, ftp)
            success: Whether parsing succeeded
        """
        self.log_lines_parsed_total.labels(
            parser=parser, success=str(success).lower()
        ).inc()

    def record_parse_error(self, parser: str, error_type: str) -> None:
        """
        Record a parsing error.

        Args:
            parser: Parser name
            error_type: Type of error
        """
        self.parse_errors_total.labels(parser=parser, error_type=error_type).inc()

    # Worker methods
    def update_workers_active(self, worker_type: str, count: int) -> None:
        """
        Update active worker count.

        Args:
            worker_type: Type of worker
            count: Number of active workers
        """
        self.workers_active.labels(worker_type=worker_type).set(count)

    def record_worker_task(self, worker_type: str, status: str) -> None:
        """
        Record a worker task completion.

        Args:
            worker_type: Type of worker
            status: Task status (success, failure)
        """
        self.worker_tasks_total.labels(worker_type=worker_type, status=status).inc()

    # Correlation methods
    def record_pattern_detected(self, pattern_type: str) -> None:
        """
        Record a detected attack pattern.

        Args:
            pattern_type: Type of pattern (brute_force, reconnaissance, etc.)
        """
        self.patterns_detected_total.labels(pattern_type=pattern_type).inc()

    def record_correlation_operation(self, operation_type: str) -> None:
        """
        Record a correlation operation.

        Args:
            operation_type: Type of operation
        """
        self.correlation_operations_total.labels(operation_type=operation_type).inc()


# Global pipeline metrics instance
_pipeline_metrics: Optional[PipelineMetrics] = None


def get_pipeline_metrics() -> PipelineMetrics:
    """
    Get global pipeline metrics instance.

    Returns:
        PipelineMetrics instance
    """
    global _pipeline_metrics
    if _pipeline_metrics is None:
        _pipeline_metrics = PipelineMetrics()
    return _pipeline_metrics
