# HP_TI Troubleshooting Guide

## Overview

This guide provides solutions for common issues encountered when deploying and operating the HP_TI platform.

## Table of Contents

1. [Deployment Issues](#deployment-issues)
2. [Service Issues](#service-issues)
3. [Database Issues](#database-issues)
4. [Elasticsearch Issues](#elasticsearch-issues)
5. [Network Issues](#network-issues)
6. [Performance Issues](#performance-issues)
7. [Logging Issues](#logging-issues)
8. [Authentication Issues](#authentication-issues)

## Deployment Issues

### Issue: Docker Compose Fails to Start Services

**Symptoms**:
```
ERROR: Service 'honeypot' failed to build
ERROR: for postgres  Cannot start service postgres
```

**Diagnosis**:
```bash
# Check Docker daemon status
sudo systemctl status docker

# Check Docker logs
sudo journalctl -u docker -n 100 --no-pager

# Verify docker-compose.yml syntax
docker-compose config

# Check available disk space
df -h

# Check Docker disk usage
docker system df
```

**Solutions**:

1. **If Docker daemon not running**:
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

2. **If disk space full**:
```bash
# Clean up Docker resources
docker system prune -af --volumes

# Or remove specific unused volumes
docker volume ls
docker volume rm <volume_name>
```

3. **If configuration syntax error**:
```bash
# Validate docker-compose.yml
docker-compose config

# Check for common issues:
# - Incorrect indentation (use spaces, not tabs)
# - Missing quotes around strings
# - Invalid port mappings
```

4. **If permission denied**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or run with sudo
sudo docker-compose up -d
```

### Issue: Container Keeps Restarting

**Symptoms**:
```bash
docker-compose ps
# Shows container status as "Restarting"
```

**Diagnosis**:
```bash
# Check container logs
docker-compose logs honeypot --tail=100

# Check container restart count
docker inspect hp_ti_honeypot | grep -A 5 "RestartCount"

# Check container exit code
docker inspect hp_ti_honeypot | grep -A 3 "State"
```

**Common Exit Codes**:
- Exit code 1: Application error (check logs)
- Exit code 137: Out of memory (OOMKilled)
- Exit code 139: Segmentation fault
- Exit code 143: Graceful termination (SIGTERM)

**Solutions**:

1. **If exit code 1 (application error)**:
```bash
# Check application logs for errors
docker-compose logs honeypot --tail=200 | grep -i "error\|exception\|traceback"

# Common causes:
# - Missing environment variables
# - Database connection failure
# - Configuration errors

# Verify .env file
cat .env

# Test database connectivity
docker exec hp_ti_postgres pg_isready -U hp_ti_user
```

2. **If exit code 137 (OOMKilled)**:
```bash
# Check memory usage
docker stats --no-stream hp_ti_honeypot

# Increase memory limit in docker-compose.yml
services:
  honeypot:
    deploy:
      resources:
        limits:
          memory: 4G  # Increase from 2G

# Restart with new limits
docker-compose up -d
```

3. **If exit code 139 (segmentation fault)**:
```bash
# Check for corrupt libraries or Python packages
docker-compose run --rm honeypot pip check

# Rebuild container
docker-compose build --no-cache honeypot
docker-compose up -d honeypot
```

### Issue: Database Initialization Fails

**Symptoms**:
```
ERROR: relation "honeypot_events" does not exist
ERROR: could not connect to server: Connection refused
```

**Solutions**:

1. **PostgreSQL not ready**:
```bash
# Wait for PostgreSQL to finish initializing
docker-compose logs postgres | grep "database system is ready to accept connections"

# If not ready, wait 30 seconds
sleep 30

# Retry initialization
docker-compose run --rm honeypot python scripts/init_database.py
```

2. **Connection refused**:
```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres --tail=100

# Verify database credentials in .env
cat .env | grep DB_

# Test connection manually
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "SELECT 1;"
```

3. **Permission denied**:
```bash
# Check PostgreSQL user permissions
docker exec hp_ti_postgres psql -U postgres -c "\du"

# Grant necessary permissions
docker exec hp_ti_postgres psql -U postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE hp_ti_db TO hp_ti_user;"
```

## Service Issues

### Issue: Honeypot Services Not Accepting Connections

**Symptoms**:
```bash
nc -zv localhost 2222
# Connection refused
```

**Diagnosis**:
```bash
# Check if container is running
docker-compose ps honeypot

# Check if ports are bound
docker port hp_ti_honeypot

# Check if service is listening
docker exec hp_ti_honeypot netstat -tlnp | grep -E "2222|8080"

# Check firewall
sudo ufw status | grep -E "2222|8080"

# Check logs
docker-compose logs honeypot --tail=100 | grep -i "listening\|started\|error"
```

**Solutions**:

1. **Service not started**:
```bash
# Check service status in logs
docker-compose logs honeypot | grep "Starting\|Started"

# If services not starting, check for errors
docker-compose logs honeypot | grep -i "error\|exception"

# Restart container
docker-compose restart honeypot
```

2. **Port already in use**:
```bash
# Check what's using the port
sudo lsof -i :2222
sudo netstat -tlnp | grep 2222

# Kill conflicting process or change port
# Edit docker-compose.yml to use different port:
ports:
  - "2223:2222"  # Map to different host port

docker-compose up -d honeypot
```

3. **Firewall blocking**:
```bash
# Check firewall rules
sudo ufw status verbose

# Allow port if blocked
sudo ufw allow 2222/tcp
sudo ufw allow 8080/tcp

# Reload firewall
sudo ufw reload
```

### Issue: High CPU Usage

**Symptoms**:
```bash
docker stats
# CPU% consistently > 80%
```

**Diagnosis**:
```bash
# Identify which container
docker stats --no-stream | sort -k 3 -h

# Check what's consuming CPU inside container
docker exec hp_ti_honeypot top -bn1

# Check for tight loops or hanging processes
docker-compose logs honeypot --tail=500 | grep -i "processing\|handling"
```

**Solutions**:

1. **Attack campaign (expected high load)**:
```bash
# Check connection rate
docker-compose logs honeypot | grep "New connection" | tail -20

# If under attack, this is normal
# Ensure system can handle load or implement rate limiting

# Add rate limiting to docker-compose.yml:
services:
  honeypot:
    deploy:
      resources:
        limits:
          cpus: '4'  # Limit CPU usage

# Or implement application-level rate limiting
# Edit config/honeypot.yaml:
rate_limiting:
  enabled: true
  max_connections_per_ip: 10
  time_window: 60  # seconds
```

2. **Bug causing infinite loop**:
```bash
# Check logs for repeated errors
docker-compose logs honeypot --tail=1000 | sort | uniq -c | sort -rn | head

# If same error repeating rapidly:
# - Review code for infinite loops
# - Check for retry logic without backoff
# - Restart service
docker-compose restart honeypot
```

3. **Database queries**:
```bash
# Check for slow queries
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pid, query_start, state, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;"

# Identify and optimize slow queries
# Add indexes, optimize query logic
```

## Database Issues

### Issue: Database Connection Pool Exhausted

**Symptoms**:
```
FATAL: remaining connection slots are reserved
ERROR: connection pool exhausted
```

**Diagnosis**:
```bash
# Check current connections
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check max connections setting
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SHOW max_connections;"

# Identify connection hogs
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pid, usename, application_name, state, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;"
```

**Solutions**:

1. **Kill idle connections**:
```bash
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '10 minutes'
  AND pid <> pg_backend_pid();"
```

2. **Increase max_connections**:
```bash
# Edit PostgreSQL config
docker exec -it hp_ti_postgres bash
echo "max_connections = 200" >> /var/lib/postgresql/data/postgresql.conf
exit

# Restart PostgreSQL
docker-compose restart postgres
```

3. **Fix connection pool in application**:
```python
# Check database.py connection pool settings
# Ensure connections are being closed properly

# Use context managers:
with get_db_connection() as conn:
    # Use connection
    pass
# Connection automatically closed

# Or implement connection pooling:
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True  # Verify connections before use
)
```

### Issue: Slow Database Queries

**Symptoms**:
```
Query execution time > 5 seconds
Application timeouts
```

**Diagnosis**:
```bash
# Enable query logging
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();"

# View slow queries
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# Analyze specific query
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
EXPLAIN ANALYZE
SELECT * FROM honeypot_events WHERE created_at > NOW() - INTERVAL '1 day';"
```

**Solutions**:

1. **Add missing indexes**:
```sql
-- Create indexes on frequently queried columns
CREATE INDEX idx_honeypot_events_created_at ON honeypot_events(created_at);
CREATE INDEX idx_honeypot_events_source_ip ON honeypot_events(source_ip);
CREATE INDEX idx_honeypot_events_service ON honeypot_events(service);

-- Composite index for common query patterns
CREATE INDEX idx_honeypot_events_service_created_at
  ON honeypot_events(service, created_at DESC);
```

2. **Optimize queries**:
```sql
-- Use LIMIT to avoid fetching too many rows
SELECT * FROM honeypot_events ORDER BY created_at DESC LIMIT 1000;

-- Use specific columns instead of SELECT *
SELECT id, source_ip, service, created_at FROM honeypot_events;

-- Use indexes efficiently
-- Bad: WHERE DATE(created_at) = '2025-01-15'
-- Good: WHERE created_at >= '2025-01-15' AND created_at < '2025-01-16'
```

3. **Database maintenance**:
```bash
# Vacuum and analyze
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "VACUUM ANALYZE;"

# Reindex if needed
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "REINDEX DATABASE hp_ti_db;"
```

## Elasticsearch Issues

### Issue: Elasticsearch Cluster Red/Yellow

**Symptoms**:
```bash
curl -s localhost:9200/_cluster/health | jq .
{
  "status": "red",
  ...
}
```

**Diagnosis**:
```bash
# Check cluster health details
curl -s "localhost:9200/_cluster/health?pretty"

# Check unassigned shards
curl -s "localhost:9200/_cat/shards?v&h=index,shard,prirep,state,unassigned.reason" | grep UNASSIGNED

# Check node status
curl -s "localhost:9200/_cat/nodes?v"

# Check disk space
curl -s "localhost:9200/_cat/allocation?v"
```

**Solutions**:

1. **Disk space issue**:
```bash
# Check disk usage
df -h /data/elasticsearch

# Delete old indices
curl -X DELETE "localhost:9200/hp_ti_logs-$(date -d '60 days ago' +%Y.%m.%d)"

# Increase disk.watermark thresholds temporarily
curl -X PUT "localhost:9200/_cluster/settings" \
  -H 'Content-Type: application/json' \
  -d '{
    "transient": {
      "cluster.routing.allocation.disk.watermark.low": "95%",
      "cluster.routing.allocation.disk.watermark.high": "97%"
    }
  }'
```

2. **Unassigned shards**:
```bash
# Retry allocation
curl -X POST "localhost:9200/_cluster/reroute?retry_failed=true"

# If specific shard stuck, manually allocate
curl -X POST "localhost:9200/_cluster/reroute" \
  -H 'Content-Type: application/json' \
  -d '{
    "commands": [{
      "allocate_replica": {
        "index": "hp_ti_logs-2025.01.15",
        "shard": 0,
        "node": "es-node-1"
      }
    }]
  }'
```

3. **Corrupted index**:
```bash
# Close and reopen index
curl -X POST "localhost:9200/hp_ti_logs-2025.01.15/_close"
sleep 10
curl -X POST "localhost:9200/hp_ti_logs-2025.01.15/_open"

# If still failing, restore from snapshot
curl -X POST "localhost:9200/_snapshot/hp_ti_backups/snapshot_latest/_restore" \
  -H 'Content-Type: application/json' \
  -d '{
    "indices": "hp_ti_logs-2025.01.15"
  }'
```

### Issue: Out of Memory Errors

**Symptoms**:
```
java.lang.OutOfMemoryError: Java heap space
Circuit breaker exceptions
```

**Diagnosis**:
```bash
# Check JVM heap usage
curl -s "localhost:9200/_nodes/stats/jvm?pretty" | grep -A 5 "heap"

# Check memory usage
docker stats hp_ti_elasticsearch --no-stream
```

**Solutions**:

1. **Increase JVM heap**:
```yaml
# Edit docker-compose.yml
services:
  elasticsearch:
    environment:
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"  # Increase from 2g
    deploy:
      resources:
        limits:
          memory: 8G  # Total container memory
```

2. **Clear field data cache**:
```bash
curl -X POST "localhost:9200/_cache/clear?fielddata=true"
```

3. **Optimize queries**:
```bash
# Avoid wildcard queries on large datasets
# Use filters instead of queries when possible
# Limit result size
```

## Network Issues

### Issue: Cannot Reach External APIs

**Symptoms**:
```
requests.exceptions.ConnectionError: Failed to establish connection
Timeout errors when calling threat intel APIs
```

**Diagnosis**:
```bash
# Test DNS resolution
docker exec hp_ti_honeypot nslookup api.abuseipdb.com

# Test HTTPS connectivity
docker exec hp_ti_honeypot curl -I https://api.abuseipdb.com

# Check firewall
sudo ufw status verbose

# Check proxy settings (if applicable)
docker exec hp_ti_honeypot env | grep -i proxy
```

**Solutions**:

1. **DNS resolution failure**:
```bash
# Configure DNS in Docker
# Edit /etc/docker/daemon.json
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}

sudo systemctl restart docker
docker-compose up -d
```

2. **Firewall blocking**:
```bash
# Allow outgoing HTTPS
sudo ufw allow out 443/tcp

# If using corporate proxy
# Set proxy in .env
HTTPS_PROXY=http://proxy.example.com:8080
HTTP_PROXY=http://proxy.example.com:8080
```

3. **API rate limiting**:
```bash
# Check API response headers
docker exec hp_ti_honeypot curl -I \
  -H "Key: your-api-key" \
  https://api.abuseipdb.com/api/v2/check?ipAddress=1.2.3.4

# Implement retry with exponential backoff
# Check config/enrichment.yaml
rate_limiting:
  retry_count: 3
  retry_delay: 5  # seconds
  exponential_backoff: true
```

## Performance Issues

### Issue: High Latency

**Symptoms**:
- Response times > 1 second
- Slow dashboard loading
- Database query timeouts

**Solutions**: See [Performance Optimization Guide](performance_optimization.md)

## Logging Issues

### Issue: Logs Not Appearing in Elasticsearch

**Symptoms**:
```bash
curl -s "localhost:9200/hp_ti_logs-*/_count"
# Returns 0 or very low count
```

**Diagnosis**:
```bash
# Check if events are being created in database
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM honeypot_events WHERE created_at > NOW() - INTERVAL '5 minutes';"

# Check pipeline logs
docker-compose logs pipeline --tail=200

# Check Elasticsearch logs
docker-compose logs elasticsearch --tail=200 | grep -i "error\|exception"
```

**Solutions**:

1. **Pipeline not running**:
```bash
docker-compose ps pipeline
# If not running, start it
docker-compose up -d pipeline
```

2. **Elasticsearch connection failure**:
```bash
# Test connection from pipeline container
docker exec hp_ti_pipeline curl -s "http://elasticsearch:9200/_cluster/health"

# Check .env variables
cat .env | grep ES_
```

3. **Index mapping conflict**:
```bash
# Check for mapping conflicts
curl -s "localhost:9200/hp_ti_logs-*/_mapping" | jq .

# Delete problematic index and recreate
curl -X DELETE "localhost:9200/hp_ti_logs-2025.01.15"
# Pipeline will recreate on next event
```

## Authentication Issues

### Issue: Cannot Connect to Database

**Symptoms**:
```
FATAL: password authentication failed for user "hp_ti_user"
```

**Solutions**:

```bash
# Verify credentials in .env
cat .env | grep DB_

# Reset password
docker exec hp_ti_postgres psql -U postgres -c \
  "ALTER USER hp_ti_user WITH PASSWORD 'new_password';"

# Update .env with new password
# Restart services
docker-compose restart
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
