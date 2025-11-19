#!/usr/bin/env python3
"""
HP_TI Load Testing Suite

Tests system performance under various load conditions.
"""

from locust import HttpUser, TaskSet, task, between, events
import random
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HoneypotBehavior(TaskSet):
    """Honeypot service behavior simulation"""

    def on_start(self):
        """Called when a simulated user starts"""
        self.source_ips = [
            f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
            for _ in range(100)
        ]
        logger.info("Simulated attacker started")

    @task(5)
    def http_honeypot_request(self):
        """Simulate HTTP request to honeypot"""
        endpoints = [
            "/",
            "/admin",
            "/login",
            "/wp-admin",
            "/phpmyadmin",
            "/config.php",
            "/.env",
            "/backup.sql"
        ]

        endpoint = random.choice(endpoints)

        with self.client.get(
            f"http://localhost:8080{endpoint}",
            headers={"User-Agent": "AttackBot/1.0"},
            name="/honeypot/http",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def ssh_honeypot_attempt(self):
        """Simulate SSH authentication attempt"""
        # Note: This tests the metrics endpoint, not actual SSH
        # For actual SSH testing, use paramiko
        with self.client.get(
            "http://localhost:9090/metrics",
            name="/honeypot/ssh_metrics",
            catch_response=True
        ) as response:
            if "honeypot_connections_total" in response.text:
                response.success()
            else:
                response.failure("Metrics not found")

    @task(2)
    def api_query(self):
        """Simulate API query"""
        with self.client.get(
            "http://localhost:9090/metrics",
            name="/metrics/query",
            catch_response=True
        ) as response:
            if response.elapsed.total_seconds() > 1.0:
                response.failure("Response too slow")
            else:
                response.success()


class AttackerUser(HttpUser):
    """Simulated attacker user"""

    tasks = [HoneypotBehavior]
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = "http://localhost"


class HighVolumeAttacker(HttpUser):
    """High-volume attacker (no wait time)"""

    tasks = [HoneypotBehavior]
    wait_time = between(0.1, 0.5)  # Aggressive attack
    host = "http://localhost"


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    logger.info("=" * 60)
    logger.info("HP_TI Load Test Starting")
    logger.info(f"Start time: {datetime.now()}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    logger.info("=" * 60)
    logger.info("HP_TI Load Test Completed")
    logger.info(f"End time: {datetime.now()}")

    # Print statistics
    stats = environment.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Median response time: {stats.total.median_response_time:.2f}ms")
    logger.info(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    logger.info(f"Requests per second: {stats.total.total_rps:.2f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    print("""
HP_TI Load Testing Suite
========================

Usage:
    # Run with web UI
    locust -f load_test.py --host=http://localhost

    # Run headless (100 users, 10 users/sec spawn rate, 5 minutes)
    locust -f load_test.py --host=http://localhost --headless -u 100 -r 10 -t 5m

    # Run specific user class
    locust -f load_test.py --host=http://localhost --headless -u 50 -r 5 HighVolumeAttacker

Performance Targets:
    - Response time p95: < 500ms
    - Response time p99: < 1000ms
    - Requests per second: > 100
    - Error rate: < 1%
    """)
