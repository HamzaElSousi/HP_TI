# HP_TI Data Pipeline Documentation

## Overview

The HP_TI data pipeline processes honeypot logs in real-time, extracting structured data and storing it in multiple backends for analysis and search.

## Architecture

```
Log Files → Log Collector → Parser → Storage Manager → Databases
                                                      ├─ PostgreSQL (structured data)
                                                      └─ Elasticsearch (full-text search)
```

## Components

### 1. Log Collector (`pipeline/ingestion/log_collector.py`)

Monitors honeypot log directories for new entries using file system events.

**Features**:
- Real-time log file monitoring using watchdog
- Handles log rotation gracefully
- Batch processing for efficiency
- Configurable flush intervals

**Usage**:
```python
from pipeline.ingestion.log_collector import LogCollector

def process_logs(file_path, new_lines):
    # Process new log lines
    pass

collector = LogCollector(log_directory=Path("logs/honeypots"), process_callback=process_logs)
collector.start()
```

### 2. Log Parsers (`threat_intel/parsers/`)

Extract structured data from JSON-formatted log entries.

**Base Parser** (`base_parser.py`):
- Abstract base class for all parsers
- Common parsing utilities
- Input sanitization
- Validation helpers

**SSH Parser** (`ssh_parser.py`):
- Parses SSH honeypot logs
- Extracts authentication attempts
- Captures command executions
- Categorizes events

**Usage**:
```python
from threat_intel.parsers.ssh_parser import SSHParser

parser = SSHParser()
entry = parser.parse_line(log_line)

if entry:
    auth_data = parser.extract_auth_attempt(entry)
    cmd_data = parser.extract_command(entry)
```

### 3. Database Models (`pipeline/storage/models.py`)

SQLAlchemy ORM models for PostgreSQL:

- **Session**: Represents an attacker session
- **AuthAttempt**: Authentication attempts with credentials
- **Command**: Commands executed by attackers
- **IPIntelligence**: Enriched IP address data
- **AttackPattern**: Detected attack patterns
- **Credential**: Unique credential pairs with statistics

**Schema Features**:
- UUID primary keys
- Indexed foreign keys for performance
- Timestamp tracking (created_at, updated_at)
- JSON fields for flexible metadata
- Relationship definitions

### 4. PostgreSQL Client (`pipeline/storage/postgres_client.py`)

Manages connections to PostgreSQL with connection pooling.

**Features**:
- SQLAlchemy ORM integration
- Connection pooling
- Context manager for transactions
- Helper methods for common queries
- Batch operations support

**Usage**:
```python
from pipeline.storage.postgres_client import PostgreSQLClient

client = PostgreSQLClient(database_url="postgresql://...")

# Create session
client.create_session(
    session_id="uuid-here",
    source_ip="192.168.1.1",
    source_port=12345,
    honeypot_service="ssh"
)

# Store auth attempt
client.create_auth_attempt(
    session_id="uuid-here",
    username="root",
    password="admin"
)

# Query stats
stats = client.get_attack_stats()
```

### 5. Elasticsearch Client (`pipeline/storage/elasticsearch_client.py`)

Manages connections to Elasticsearch for log storage and search.

**Features**:
- Index template management
- Time-series index creation
- Bulk indexing for performance
- Full-text search capabilities
- Index lifecycle management

**Usage**:
```python
from pipeline.storage.elasticsearch_client import ElasticsearchClient

client = ElasticsearchClient(url="http://localhost:9200", index_prefix="hp_ti")

# Create index templates
client.create_index_templates()

# Index documents
client.index_document({"timestamp": "...", "message": "..."})

# Bulk index
client.bulk_index([doc1, doc2, doc3])

# Search
results = client.search_by_ip("192.168.1.1")
```

### 6. Storage Manager (`pipeline/storage/storage_manager.py`)

Coordinates storage across PostgreSQL and Elasticsearch.

**Features**:
- Unified interface for both backends
- Automatic parsing and routing
- Transaction management
- Error handling and retry logic
- Statistics and analytics

**Usage**:
```python
from pipeline.storage.storage_manager import StorageManager

manager = StorageManager(postgres_client, elasticsearch_client)

# Process log entries
stats = manager.process_ssh_log_entries(log_lines)

# Get session details
details = manager.get_session_details(session_id)

# Get attack summary
summary = manager.get_attack_summary()
```

## Data Flow

### 1. Log Entry Creation

Honeypot creates JSON log entry:

```json
{
  "timestamp": "2025-11-19T12:30:45.123Z",
  "level": "INFO",
  "component": "ssh_honeypot",
  "event_type": "auth_attempt",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_ip": "192.168.1.100",
  "username": "root",
  "password": "admin123"
}
```

### 2. Detection and Collection

Log collector detects new entry:
- Watches `logs/honeypots/*.log` files
- Reads new lines from file
- Batches entries for efficiency

### 3. Parsing

SSH parser extracts structured data:
- Validates JSON format
- Extracts event-specific fields
- Sanitizes input data
- Creates typed objects

### 4. Storage

Storage manager routes data:

**PostgreSQL**:
- Sessions → `sessions` table
- Auth attempts → `auth_attempts` table
- Commands → `commands` table

**Elasticsearch**:
- All logs → `hp_ti-logs-YYYY-MM-DD` index
- Full-text searchable
- Aggregation ready

## Database Initialization

### First-Time Setup

```bash
# Make sure databases are running
cd deployment/docker
docker-compose up -d postgres elasticsearch

# Initialize schemas
python scripts/init_database.py
```

This will:
1. Create all PostgreSQL tables
2. Set up Elasticsearch index templates
3. Configure index lifecycle policies

### Manual Schema Creation

```python
from pipeline.storage.postgres_client import PostgreSQLClient

client = PostgreSQLClient(database_url="...")
client.create_tables()
```

## Data Retention

### Elasticsearch

Indices are created daily with pattern: `hp_ti-logs-YYYY-MM-DD`

Cleanup old indices:

```python
client.delete_old_indices(days_to_keep=30)
```

### PostgreSQL

Implement custom retention policies based on:
- Data volume
- Compliance requirements
- Storage capacity

Example cleanup (implement as needed):
```sql
DELETE FROM commands WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM auth_attempts WHERE timestamp < NOW() - INTERVAL '90 days';
DELETE FROM sessions WHERE start_time < NOW() - INTERVAL '90 days';
```

## Performance Tuning

### Batch Processing

Use batch operations for better performance:

```python
# Elasticsearch bulk index
client.bulk_index(documents, index_type="logs")

# Process multiple log entries together
storage_manager.process_ssh_log_entries(batch_of_lines)
```

### Connection Pooling

Configure pool sizes based on workload:

```python
PostgreSQLClient(
    database_url=url,
    pool_size=20,        # Active connections
    max_overflow=40,     # Additional connections under load
    pool_timeout=30      # Wait time for connection
)
```

### Indexing

Key PostgreSQL indexes:
- `sessions(source_ip, start_time)`
- `auth_attempts(username, password)`
- `auth_attempts(timestamp)`
- `ip_intelligence(country_code)`
- `ip_intelligence(abuse_confidence_score)`

## Querying Data

### Get Attack Statistics

```python
# Summary stats
stats = postgres_client.get_attack_stats(
    start_time=datetime(2025, 11, 1),
    end_time=datetime(2025, 11, 30)
)

# Common credentials
creds = postgres_client.get_common_credentials(limit=100)

# Common commands
cmds = postgres_client.get_common_commands(limit=100)
```

### Search Logs

```python
# By IP
logs = es_client.search_by_ip("192.168.1.1")

# By session
logs = es_client.search_by_session(session_id)

# By date range
logs = es_client.search_by_date_range(start_time, end_time)

# Custom query
logs = es_client.search({
    "bool": {
        "must": [
            {"term": {"event_type": "auth_attempt"}},
            {"term": {"success": False}}
        ]
    }
})
```

### Complete Session View

```python
# Get everything about a session
details = storage_manager.get_session_details(session_id)

# Returns:
# {
#     "session": {...},
#     "auth_attempts": [...],
#     "commands": [...],
#     "logs": [...]
# }
```

## Monitoring

### Pipeline Health

Monitor these metrics:
- Log processing rate (entries/second)
- Parse success/failure rate
- Database write latency
- Elasticsearch indexing speed
- Queue depths and backlogs

### Database Health

**PostgreSQL**:
- Connection pool utilization
- Query performance
- Table sizes and growth
- Index efficiency

**Elasticsearch**:
- Index sizes and shard count
- Query latency
- Disk usage
- Cluster health

## Troubleshooting

### Logs Not Being Processed

1. Check log collector is running
2. Verify file permissions
3. Check log file format (must be JSON)
4. Review parser error logs

### Database Connection Issues

```python
# Test PostgreSQL
from pipeline.storage.postgres_client import PostgreSQLClient
client = PostgreSQLClient(database_url="...")
with client.get_session() as session:
    print("Connection OK")

# Test Elasticsearch
from pipeline.storage.elasticsearch_client import ElasticsearchClient
client = ElasticsearchClient(url="...")
print(f"Cluster health: {client.client.cluster.health()}")
```

### Parse Failures

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check for:
- Invalid JSON format
- Missing required fields
- Data type mismatches
- Encoding issues

## Next Steps

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for Phase 3:
- Threat intelligence enrichment
- External API integrations
- IP reputation scoring
- Correlation engine
