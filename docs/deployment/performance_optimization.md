# HP_TI Performance Optimization Guide

## Overview

This guide provides strategies and techniques for optimizing the performance of the HP_TI platform to handle high connection rates and large data volumes efficiently.

## Performance Baseline

### Baseline Metrics

Establish baseline performance metrics before optimization:

| Metric | Baseline Target | Optimized Target |
|--------|----------------|------------------|
| **Request Latency (p95)** | < 500ms | < 200ms |
| **Request Latency (p99)** | < 1000ms | < 500ms |
| **Connection Rate** | 100 conn/sec | 1000 conn/sec |
| **Event Processing Rate** | 1000 events/sec | 5000 events/sec |
| **Database Query Time** | < 100ms | < 50ms |
| **Elasticsearch Query Time** | < 500ms | < 200ms |
| **Memory Usage** | < 75% | < 60% |
| **CPU Usage** | < 70% | < 50% |
| **Disk I/O Wait** | < 10% | < 5% |

### Measuring Baseline

```bash
# Capture current performance metrics
./scripts/performance_benchmark.sh > baseline_$(date +%Y%m%d).txt

# Or manually:

# 1. Request latency
curl -s http://localhost:9090/metrics | grep honeypot_request_duration_seconds

# 2. Connection rate
docker-compose logs honeypot | grep "New connection" | wc -l

# 3. Event processing rate
curl -s http://localhost:9091/metrics | grep pipeline_events_processed_total

# 4. Database query performance
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT query, calls, total_time, mean_time, max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# 5. Resource utilization
docker stats --no-stream
```

## Database Optimization

### 1. Query Optimization

#### Identify Slow Queries

```bash
# Enable pg_stat_statements extension
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Find slowest queries
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT
  substring(query, 1, 50) AS short_query,
  round(total_time::numeric, 2) AS total_time,
  calls,
  round(mean_time::numeric, 2) AS mean,
  round((100 * total_time / sum(total_time) OVER ())::numeric, 2) AS percentage_cpu
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;"
```

#### Optimize Common Queries

**Before** (Slow):
```sql
-- Slow: Full table scan
SELECT * FROM honeypot_events
WHERE DATE(created_at) = '2025-01-15';
```

**After** (Fast):
```sql
-- Fast: Uses index
SELECT id, source_ip, service, created_at
FROM honeypot_events
WHERE created_at >= '2025-01-15 00:00:00'
  AND created_at < '2025-01-16 00:00:00';
```

### 2. Index Optimization

#### Create Strategic Indexes

```sql
-- Most frequently queried columns
CREATE INDEX CONCURRENTLY idx_honeypot_events_created_at
  ON honeypot_events (created_at DESC);

CREATE INDEX CONCURRENTLY idx_honeypot_events_source_ip
  ON honeypot_events (source_ip);

CREATE INDEX CONCURRENTLY idx_honeypot_events_service
  ON honeypot_events (service);

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY idx_honeypot_events_service_created
  ON honeypot_events (service, created_at DESC);

CREATE INDEX CONCURRENTLY idx_honeypot_events_ip_created
  ON honeypot_events (source_ip, created_at DESC);

-- Partial indexes for specific queries
CREATE INDEX CONCURRENTLY idx_honeypot_events_attacks
  ON honeypot_events (created_at DESC)
  WHERE attack_detected = true;

-- Hash index for equality comparisons
CREATE INDEX CONCURRENTLY idx_honeypot_events_session_hash
  ON honeypot_events USING hash (session_id);

-- GIN index for JSONB columns
CREATE INDEX CONCURRENTLY idx_honeypot_events_metadata_gin
  ON honeypot_events USING gin (metadata);
```

#### Analyze Index Usage

```sql
-- Find unused indexes
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexrelid IS NOT NULL
ORDER BY pg_relation_size(indexrelid) DESC;

-- Drop unused indexes
-- DROP INDEX CONCURRENTLY index_name;
```

### 3. Table Partitioning

#### Partition by Time (Recommended for Logs)

```sql
-- Create partitioned table
CREATE TABLE honeypot_events_partitioned (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    source_ip INET NOT NULL,
    service VARCHAR(50) NOT NULL,
    -- ... other columns
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create partitions (monthly)
CREATE TABLE honeypot_events_2025_01 PARTITION OF honeypot_events_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE honeypot_events_2025_02 PARTITION OF honeypot_events_partitioned
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Create indexes on partitions
CREATE INDEX idx_events_2025_01_timestamp
  ON honeypot_events_2025_01 (timestamp DESC);

CREATE INDEX idx_events_2025_01_source_ip
  ON honeypot_events_2025_01 (source_ip);

-- Automated partition management with pg_partman
CREATE EXTENSION pg_partman;

SELECT create_parent(
  'public.honeypot_events_partitioned',
  'timestamp',
  'native',
  'monthly',
  p_premake := 3  -- Pre-create 3 months ahead
);

-- Schedule automatic partition creation
SELECT update_partition_auto_append('public.honeypot_events_partitioned');
```

**Benefits**:
- Faster queries (scan only relevant partitions)
- Easier data archival (drop old partitions)
- Improved vacuum performance

### 4. Connection Pooling

#### Configure PgBouncer

```bash
# Install PgBouncer
sudo apt-get install pgbouncer

# Configure /etc/pgbouncer/pgbouncer.ini
cat > /etc/pgbouncer/pgbouncer.ini <<EOF
[databases]
hp_ti_db = host=localhost port=5432 dbname=hp_ti_db

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 100
max_user_connections = 100
EOF

# Create userlist
echo '"hp_ti_user" "md5<password_hash>"' > /etc/pgbouncer/userlist.txt

# Start PgBouncer
sudo systemctl start pgbouncer

# Update application to use PgBouncer
# Change DB_PORT from 5432 to 6432 in .env
```

#### Application-Level Connection Pooling

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,            # Number of connections to maintain
    max_overflow=10,         # Max additional connections
    pool_timeout=30,         # Timeout waiting for connection
    pool_recycle=3600,       # Recycle connections after 1 hour
    pool_pre_ping=True,      # Verify connection health before use
    echo_pool=False,         # Set True for debugging
)

# Always use context managers
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage
with get_db_connection() as conn:
    result = conn.execute("SELECT * FROM honeypot_events LIMIT 10")
    # Connection automatically closed
```

### 5. Database Configuration Tuning

```bash
# PostgreSQL configuration for performance
# Edit postgresql.conf

# Memory settings (for 32GB RAM server)
shared_buffers = 8GB                # 25% of total RAM
effective_cache_size = 24GB         # 75% of total RAM
maintenance_work_mem = 2GB
work_mem = 64MB                     # For complex queries

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
max_wal_size = 4GB
min_wal_size = 1GB

# Query planning
random_page_cost = 1.1              # For SSD storage
effective_io_concurrency = 200      # For SSD storage
default_statistics_target = 100

# Logging (for performance analysis)
log_min_duration_statement = 1000   # Log queries > 1 second
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Restart PostgreSQL
docker-compose restart postgres
```

### 6. Regular Maintenance

```bash
# Automated maintenance script
cat > /opt/hp_ti/scripts/db_maintenance.sh <<'EOF'
#!/bin/bash

# Vacuum and analyze (reclaim space and update statistics)
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "VACUUM ANALYZE;"

# Reindex if fragmentation detected
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Archive old partitions (keep 90 days)
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT drop_partition_retention('public.honeypot_events_partitioned', '90 days');"

echo "Database maintenance completed at $(date)"
EOF

chmod +x /opt/hp_ti/scripts/db_maintenance.sh

# Schedule weekly maintenance
crontab -e
# Add: 0 3 * * 0 /opt/hp_ti/scripts/db_maintenance.sh >> /var/log/hp_ti/db_maintenance.log 2>&1
```

## Elasticsearch Optimization

### 1. Index Settings

```bash
# Optimize index settings for performance
curl -X PUT "localhost:9200/hp_ti_logs-*/_settings" \
  -H 'Content-Type: application/json' \
  -d '{
    "index": {
      "refresh_interval": "30s",           # Reduce refresh frequency (default: 1s)
      "number_of_replicas": 1,             # Balance durability vs performance
      "translog.durability": "async",      # Async translog for higher throughput
      "translog.sync_interval": "30s"
    }
  }'

# For bulk ingestion, temporarily disable refresh
curl -X PUT "localhost:9200/hp_ti_logs-*/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"refresh_interval": "-1"}}'

# Re-enable after bulk ingestion
curl -X PUT "localhost:9200/hp_ti_logs-*/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"refresh_interval": "30s"}}'
```

### 2. Bulk Indexing

```python
# Use bulk API for high throughput
from elasticsearch import Elasticsearch, helpers

es = Elasticsearch(['http://localhost:9200'])

def bulk_index_events(events):
    """Bulk index events to Elasticsearch"""
    actions = [
        {
            "_index": f"hp_ti_logs-{event['timestamp'].strftime('%Y.%m.%d')}",
            "_source": event
        }
        for event in events
    ]

    # Use helpers.bulk for efficient bulk indexing
    success, failed = helpers.bulk(
        es,
        actions,
        chunk_size=1000,      # Process 1000 docs at a time
        request_timeout=30,
        raise_on_error=False
    )

    return success, failed

# Batch events before indexing
event_batch = []
BATCH_SIZE = 1000

for event in event_stream:
    event_batch.append(event)

    if len(event_batch) >= BATCH_SIZE:
        bulk_index_events(event_batch)
        event_batch = []

# Index remaining events
if event_batch:
    bulk_index_events(event_batch)
```

### 3. Query Optimization

```bash
# Use filters instead of queries (filters are cacheable)
# Bad: Full text query for exact match
curl -X GET "localhost:9200/hp_ti_logs-*/_search" \
  -d '{"query": {"match": {"service": "ssh"}}}'

# Good: Filter for exact match
curl -X GET "localhost:9200/hp_ti_logs-*/_search" \
  -d '{
    "query": {
      "bool": {
        "filter": [
          {"term": {"service": "ssh"}}
        ]
      }
    }
  }'

# Use query cache for repeated queries
curl -X GET "localhost:9200/hp_ti_logs-*/_search?request_cache=true" \
  -d '{
    "query": {
      "bool": {
        "filter": [
          {"range": {"timestamp": {"gte": "now-1h"}}}
        ]
      }
    }
  }'
```

### 4. Shard Optimization

```bash
# Right-size shards (target 20-50GB per shard)
# Too many small shards = overhead
# Too few large shards = poor distribution

# Check shard sizes
curl -s "localhost:9200/_cat/shards?v&h=index,shard,prirep,store&s=store:desc"

# Shrink index (reduce shard count)
curl -X POST "localhost:9200/hp_ti_logs-2025.01.01/_shrink/hp_ti_logs-2025.01.01-shrink" \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {
      "index.number_of_replicas": 1,
      "index.number_of_shards": 1
    }
  }'

# Force merge to reduce segment count
curl -X POST "localhost:9200/hp_ti_logs-2024.*/_forcemerge?max_num_segments=1"
```

### 5. JVM and Memory Tuning

```yaml
# docker-compose.yml
services:
  elasticsearch:
    environment:
      # Set JVM heap to 50% of container memory (max 31GB)
      - "ES_JAVA_OPTS=-Xms8g -Xmx8g"
    deploy:
      resources:
        limits:
          memory: 16G  # Total container memory
        reservations:
          memory: 16G
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
```

```bash
# Monitor JVM heap usage
curl -s "localhost:9200/_nodes/stats/jvm?pretty" | \
  jq '.nodes[] | {name: .name, heap_used_percent: .jvm.mem.heap_used_percent}'

# Monitor garbage collection
curl -s "localhost:9200/_nodes/stats/jvm?pretty" | \
  jq '.nodes[] | .jvm.gc.collectors'
```

## Application Optimization

### 1. Async Processing

```python
# Use asyncio for concurrent operations
import asyncio
import aiohttp

async def enrich_ip(session, ip_address):
    """Async IP enrichment"""
    async with session.get(
        f"https://api.abuseipdb.com/api/v2/check",
        params={"ipAddress": ip_address},
        headers={"Key": API_KEY}
    ) as response:
        return await response.json()

async def enrich_batch(ip_addresses):
    """Enrich multiple IPs concurrently"""
    async with aiohttp.ClientSession() as session:
        tasks = [enrich_ip(session, ip) for ip in ip_addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

# Process 100 IPs concurrently instead of sequentially
ips = ["1.2.3.4", "5.6.7.8", ...]  # 100 IPs
results = asyncio.run(enrich_batch(ips))
# Sequential: 100 requests × 200ms = 20 seconds
# Async: 200ms (all concurrent)
```

### 2. Caching

```python
# Implement multi-level caching
import redis
from functools import lru_cache
from datetime import timedelta

# L1: In-memory LRU cache (process-local)
@lru_cache(maxsize=10000)
def get_country_code(ip_address):
    """Fast in-memory cache for frequently accessed data"""
    return geoip_lookup(ip_address)

# L2: Redis cache (shared across processes)
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

def get_ip_reputation(ip_address):
    """Cached IP reputation lookup"""
    cache_key = f"ip_reputation:{ip_address}"

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss: fetch from API
    result = abuseipdb_api_call(ip_address)

    # Cache result for 24 hours
    redis_client.setex(
        cache_key,
        timedelta(hours=24),
        json.dumps(result)
    )

    return result

# Cache warming: pre-populate cache with common IPs
def warm_cache():
    """Pre-populate cache with top attackers"""
    top_ips = db.query("SELECT DISTINCT source_ip FROM honeypot_events LIMIT 1000")
    for ip in top_ips:
        get_ip_reputation(ip)
```

### 3. Rate Limiting and Backpressure

```python
# Implement rate limiting for external APIs
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=1000, period=86400)  # 1000 calls per day
def abuseipdb_api_call(ip_address):
    """Rate-limited API call"""
    response = requests.get(
        "https://api.abuseipdb.com/api/v2/check",
        params={"ipAddress": ip_address},
        headers={"Key": API_KEY}
    )
    return response.json()

# Implement backpressure for event processing
from queue import Queue
from threading import Thread

event_queue = Queue(maxsize=10000)  # Limit queue size

def event_producer():
    """Produce events"""
    for event in event_stream:
        # Blocks if queue is full (backpressure)
        event_queue.put(event)

def event_consumer():
    """Consume and process events"""
    while True:
        event = event_queue.get()
        process_event(event)
        event_queue.task_done()

# Start producer and consumer threads
Thread(target=event_producer, daemon=True).start()
for _ in range(4):  # 4 consumer threads
    Thread(target=event_consumer, daemon=True).start()
```

### 4. Batch Processing

```python
# Batch database inserts
events_batch = []
BATCH_SIZE = 1000

for event in event_stream:
    events_batch.append(event)

    if len(events_batch) >= BATCH_SIZE:
        # Bulk insert
        db.bulk_insert(events_batch)
        events_batch = []

# Insert remaining events
if events_batch:
    db.bulk_insert(events_batch)

# SQLAlchemy bulk insert
from sqlalchemy.orm import Session

def bulk_insert_events(session: Session, events: list):
    """Efficiently insert multiple events"""
    session.bulk_insert_mappings(HoneypotEvent, events)
    session.commit()

# Much faster than:
# for event in events:
#     session.add(HoneypotEvent(**event))
#     session.commit()  # Don't commit each insert!
```

## Network Optimization

### 1. Connection Keep-Alive

```python
# Use connection pooling for HTTP requests
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)

# Mount adapter with retry and connection pooling
adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=100,  # Number of connection pools
    pool_maxsize=100       # Max connections per pool
)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Reuse session for all requests
response = session.get("https://api.example.com/data")
```

### 2. DNS Caching

```python
# Cache DNS lookups
import socket
from functools import lru_cache

@lru_cache(maxsize=1000)
def resolve_hostname(hostname):
    """Cached DNS lookup"""
    return socket.gethostbyname(hostname)
```

## Monitoring and Profiling

### 1. Application Profiling

```python
# Profile Python code
import cProfile
import pstats

def profile_function():
    """Profile specific function"""
    profiler = cProfile.Profile()
    profiler.enable()

    # Code to profile
    process_events()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 functions

# Or use line_profiler for line-by-line analysis
# pip install line_profiler
# Add @profile decorator to function
# kernprof -l -v script.py
```

### 2. Performance Metrics

```python
# Instrument code with metrics
from prometheus_client import Counter, Histogram, Gauge
import time

request_duration = Histogram(
    'request_processing_seconds',
    'Time spent processing request',
    ['endpoint']
)

request_count = Counter(
    'requests_total',
    'Total request count',
    ['endpoint', 'status']
)

@request_duration.labels(endpoint='/api/events').time()
def handle_request():
    """Automatically tracked request duration"""
    # Process request
    result = process()
    request_count.labels(endpoint='/api/events', status='success').inc()
    return result
```

## Performance Testing

### Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class HoneypotUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def connect_ssh(self):
        """Simulate SSH connection"""
        self.client.get("/ssh", timeout=5)

    @task(1)
    def connect_http(self):
        """Simulate HTTP connection"""
        self.client.get("/", timeout=5)

# Run load test
# locust -f locustfile.py --host=http://honeypot.example.com
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
