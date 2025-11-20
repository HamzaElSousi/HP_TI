#!/usr/bin/env python3
"""
HP_TI Performance Benchmarking

Measures baseline performance and identifies bottlenecks.
"""

import time
import psycopg2
import redis
import requests
from elasticsearch import Elasticsearch
from statistics import mean, median, stdev
from datetime import datetime
import json
import sys


class PerformanceBenchmark:
    """Performance benchmarking suite"""

    def __init__(self):
        self.results = {}

    def run_all_benchmarks(self):
        """Run all performance benchmarks"""
        print("=" * 60)
        print("HP_TI Performance Benchmark Suite")
        print(f"Timestamp: {datetime.now()}")
        print("=" * 60)

        self.benchmark_database()
        self.benchmark_redis()
        self.benchmark_elasticsearch()
        self.benchmark_api()

        self.print_results()
        self.save_results()

    def benchmark_database(self):
        """Benchmark PostgreSQL performance"""
        print("\n[1/4] Benchmarking PostgreSQL...")

        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="hp_ti_db",
                user="hp_ti_user",
                password="your_password"
            )
            cursor = conn.cursor()

            # Test 1: Simple SELECT
            times = []
            for _ in range(100):
                start = time.time()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                times.append((time.time() - start) * 1000)

            self.results['db_simple_query_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)],
                'min': min(times),
                'max': max(times)
            }

            # Test 2: COUNT query
            start = time.time()
            cursor.execute("SELECT count(*) FROM honeypot_events")
            count = cursor.fetchone()[0]
            elapsed = (time.time() - start) * 1000
            self.results['db_count_query_ms'] = elapsed
            self.results['db_row_count'] = count

            # Test 3: Recent events query (common use case)
            times = []
            for _ in range(10):
                start = time.time()
                cursor.execute("""
                    SELECT * FROM honeypot_events
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    ORDER BY created_at DESC
                    LIMIT 100
                """)
                cursor.fetchall()
                times.append((time.time() - start) * 1000)

            self.results['db_recent_events_query_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)]
            }

            # Test 4: Index usage check
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
                LIMIT 10
            """)
            self.results['db_top_indexes'] = cursor.fetchall()

            # Test 5: Table sizes
            cursor.execute("""
                SELECT
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 5
            """)
            self.results['db_table_sizes'] = cursor.fetchall()

            cursor.close()
            conn.close()

            print("  ✓ PostgreSQL benchmark complete")

        except Exception as e:
            print(f"  ✗ PostgreSQL benchmark failed: {e}")
            self.results['db_error'] = str(e)

    def benchmark_redis(self):
        """Benchmark Redis performance"""
        print("\n[2/4] Benchmarking Redis...")

        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)

            # Test 1: PING
            times = []
            for _ in range(1000):
                start = time.time()
                r.ping()
                times.append((time.time() - start) * 1000)

            self.results['redis_ping_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)]
            }

            # Test 2: SET operations
            times = []
            for i in range(1000):
                start = time.time()
                r.set(f'benchmark_key_{i}', f'value_{i}')
                times.append((time.time() - start) * 1000)

            self.results['redis_set_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)]
            }

            # Test 3: GET operations
            times = []
            for i in range(1000):
                start = time.time()
                r.get(f'benchmark_key_{i}')
                times.append((time.time() - start) * 1000)

            self.results['redis_get_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)]
            }

            # Cleanup
            for i in range(1000):
                r.delete(f'benchmark_key_{i}')

            # Test 4: Memory usage
            info = r.info('memory')
            self.results['redis_memory_used_mb'] = info['used_memory'] / (1024 * 1024)
            self.results['redis_memory_peak_mb'] = info['used_memory_peak'] / (1024 * 1024)

            print("  ✓ Redis benchmark complete")

        except Exception as e:
            print(f"  ✗ Redis benchmark failed: {e}")
            self.results['redis_error'] = str(e)

    def benchmark_elasticsearch(self):
        """Benchmark Elasticsearch performance"""
        print("\n[3/4] Benchmarking Elasticsearch...")

        try:
            es = Elasticsearch(['http://localhost:9200'])

            # Test 1: Cluster health
            health = es.cluster.health()
            self.results['es_cluster_status'] = health['status']
            self.results['es_nodes'] = health['number_of_nodes']
            self.results['es_shards'] = health['active_shards']

            # Test 2: Count documents
            start = time.time()
            count = es.count(index='hp_ti_logs-*')['count']
            elapsed = (time.time() - start) * 1000
            self.results['es_count_query_ms'] = elapsed
            self.results['es_document_count'] = count

            # Test 3: Search query performance
            times = []
            for _ in range(10):
                start = time.time()
                es.search(
                    index='hp_ti_logs-*',
                    body={
                        'query': {'match_all': {}},
                        'size': 100,
                        'sort': [{'timestamp': 'desc'}]
                    }
                )
                times.append((time.time() - start) * 1000)

            self.results['es_search_query_ms'] = {
                'mean': mean(times),
                'median': median(times),
                'p95': sorted(times)[int(len(times) * 0.95)]
            }

            # Test 4: Aggregation query performance
            start = time.time()
            es.search(
                index='hp_ti_logs-*',
                body={
                    'size': 0,
                    'aggs': {
                        'services': {
                            'terms': {'field': 'service.keyword'}
                        }
                    }
                }
            )
            elapsed = (time.time() - start) * 1000
            self.results['es_aggregation_query_ms'] = elapsed

            # Test 5: Index stats
            stats = es.indices.stats(index='hp_ti_logs-*')
            total_size = stats['_all']['total']['store']['size_in_bytes']
            self.results['es_index_size_gb'] = total_size / (1024**3)

            print("  ✓ Elasticsearch benchmark complete")

        except Exception as e:
            print(f"  ✗ Elasticsearch benchmark failed: {e}")
            self.results['es_error'] = str(e)

    def benchmark_api(self):
        """Benchmark API/Metrics endpoints"""
        print("\n[4/4] Benchmarking API endpoints...")

        try:
            # Test 1: Honeypot metrics endpoint
            times = []
            for _ in range(100):
                start = time.time()
                response = requests.get('http://localhost:9090/metrics', timeout=5)
                times.append((time.time() - start) * 1000)

            if response.status_code == 200:
                self.results['api_honeypot_metrics_ms'] = {
                    'mean': mean(times),
                    'median': median(times),
                    'p95': sorted(times)[int(len(times) * 0.95)]
                }

            # Test 2: Pipeline metrics endpoint
            times = []
            for _ in range(100):
                start = time.time()
                response = requests.get('http://localhost:9091/metrics', timeout=5)
                times.append((time.time() - start) * 1000)

            if response.status_code == 200:
                self.results['api_pipeline_metrics_ms'] = {
                    'mean': mean(times),
                    'median': median(times),
                    'p95': sorted(times)[int(len(times) * 0.95)]
                }

            print("  ✓ API benchmark complete")

        except Exception as e:
            print(f"  ✗ API benchmark failed: {e}")
            self.results['api_error'] = str(e)

    def print_results(self):
        """Print benchmark results"""
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)

        # Database results
        print("\nPostgreSQL Performance:")
        if 'db_simple_query_ms' in self.results:
            print(f"  Simple query (mean): {self.results['db_simple_query_ms']['mean']:.2f}ms")
            print(f"  Simple query (p95): {self.results['db_simple_query_ms']['p95']:.2f}ms")
        if 'db_count_query_ms' in self.results:
            print(f"  COUNT query: {self.results['db_count_query_ms']:.2f}ms")
            print(f"  Total rows: {self.results.get('db_row_count', 'N/A'):,}")
        if 'db_recent_events_query_ms' in self.results:
            print(f"  Recent events query (mean): {self.results['db_recent_events_query_ms']['mean']:.2f}ms")
            print(f"  Recent events query (p95): {self.results['db_recent_events_query_ms']['p95']:.2f}ms")

        # Redis results
        print("\nRedis Performance:")
        if 'redis_ping_ms' in self.results:
            print(f"  PING (mean): {self.results['redis_ping_ms']['mean']:.3f}ms")
        if 'redis_set_ms' in self.results:
            print(f"  SET (mean): {self.results['redis_set_ms']['mean']:.3f}ms")
        if 'redis_get_ms' in self.results:
            print(f"  GET (mean): {self.results['redis_get_ms']['mean']:.3f}ms")
        if 'redis_memory_used_mb' in self.results:
            print(f"  Memory used: {self.results['redis_memory_used_mb']:.2f}MB")

        # Elasticsearch results
        print("\nElasticsearch Performance:")
        if 'es_cluster_status' in self.results:
            print(f"  Cluster status: {self.results['es_cluster_status']}")
        if 'es_document_count' in self.results:
            print(f"  Total documents: {self.results['es_document_count']:,}")
        if 'es_search_query_ms' in self.results:
            print(f"  Search query (mean): {self.results['es_search_query_ms']['mean']:.2f}ms")
            print(f"  Search query (p95): {self.results['es_search_query_ms']['p95']:.2f}ms")
        if 'es_aggregation_query_ms' in self.results:
            print(f"  Aggregation query: {self.results['es_aggregation_query_ms']:.2f}ms")
        if 'es_index_size_gb' in self.results:
            print(f"  Index size: {self.results['es_index_size_gb']:.2f}GB")

        # API results
        print("\nAPI Performance:")
        if 'api_honeypot_metrics_ms' in self.results:
            print(f"  Honeypot metrics (mean): {self.results['api_honeypot_metrics_ms']['mean']:.2f}ms")
            print(f"  Honeypot metrics (p95): {self.results['api_honeypot_metrics_ms']['p95']:.2f}ms")
        if 'api_pipeline_metrics_ms' in self.results:
            print(f"  Pipeline metrics (mean): {self.results['api_pipeline_metrics_ms']['mean']:.2f}ms")

        print("\n" + "=" * 60)

    def save_results(self):
        """Save results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'benchmark_results_{timestamp}.json'

        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': self.results
            }, f, indent=2, default=str)

        print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
