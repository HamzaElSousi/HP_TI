# HP_TI Incident Response Playbook

## Overview

This playbook provides step-by-step procedures for responding to incidents affecting the HP_TI platform.

## Incident Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **P0 - Critical** | Complete system outage | Immediate | All services down, data loss |
| **P1 - High** | Major functionality impaired | < 15 minutes | Database unavailable, honeypot offline |
| **P2 - Medium** | Degraded performance | < 1 hour | Slow queries, high latency |
| **P3 - Low** | Minor issues | < 4 hours | Non-critical alerts, cosmetic issues |
| **P4 - Informational** | No immediate action required | Next business day | Enhancement requests |

## Incident Response Team

### Roles and Responsibilities

- **Incident Commander**: Overall coordination and decision-making
- **Technical Lead**: Hands-on troubleshooting and resolution
- **Communications Lead**: Stakeholder updates and documentation
- **Security Lead**: Security-related incidents and forensics

### Contact Information

```
Incident Commander: [Name] - [Phone] - [Email]
Technical Lead:     [Name] - [Phone] - [Email]
Communications:     [Name] - [Phone] - [Email]
Security Lead:      [Name] - [Phone] - [Email]
Escalation Path:    [Manager] - [Phone] - [Email]
```

## Incident Response Process

### 1. Detection and Alerting

**Alert Sources**:
- Prometheus alerts
- Grafana dashboards
- Health check failures
- User reports
- Monitoring systems

**Initial Assessment**:
```bash
# Check system status
./deployment/scripts/health_check.sh

# Check Docker services
docker-compose ps

# Check recent logs
docker-compose logs --tail=100 --since=30m

# Check Prometheus alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

### 2. Incident Declaration

**Criteria for Declaring Incident**:
- Any P0 or P1 severity issue
- Multiple P2 issues affecting same component
- Potential security breach
- Data integrity concerns

**Incident Declaration Checklist**:
- [ ] Assign severity level
- [ ] Assign incident commander
- [ ] Create incident ticket/document
- [ ] Notify response team
- [ ] Start incident timeline log

### 3. Initial Response

**Immediate Actions** (First 5 minutes):
```bash
# 1. Assess current state
./deployment/scripts/health_check.sh

# 2. Check resource utilization
docker stats --no-stream

# 3. Check disk space
df -h

# 4. Check memory
free -h

# 5. Check recent errors
docker-compose logs --tail=500 | grep -i "error\|critical\|exception"
```

**Stabilization Actions**:
- If service down: Attempt restart
- If resource exhaustion: Scale up or clear resources
- If database issues: Switch to read-only mode
- If security breach: Isolate affected components

### 4. Diagnosis and Investigation

**Diagnostic Commands**:
```bash
# Database connectivity
docker exec hp_ti_postgres pg_isready -U hp_ti_user

# Database performance
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pid, usename, state, query_start, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;"

# Elasticsearch health
curl -s http://localhost:9200/_cluster/health?pretty

# Redis connectivity
docker exec hp_ti_redis redis-cli ping

# Check honeypot service status
curl -s http://localhost:9090/metrics | grep honeypot_service_up

# Check pipeline metrics
curl -s http://localhost:9091/metrics | grep pipeline_events_processed_total
```

**Log Analysis**:
```bash
# Application logs
docker-compose logs honeypot --tail=1000 | less

# Database logs
docker-compose logs postgres --tail=500 | grep -i "error\|fatal"

# Elasticsearch logs
docker-compose logs elasticsearch --tail=500

# System logs
journalctl -u docker -n 500 --no-pager
```

### 5. Resolution Actions

#### Service Restart
```bash
# Restart specific service
docker-compose restart honeypot

# Restart all services
docker-compose restart

# Full restart (removes containers)
docker-compose down
docker-compose up -d
```

#### Database Issues
```bash
# Check connections
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Kill long-running queries
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '5 minutes'
  AND pid <> pg_backend_pid();"

# Vacuum database
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "VACUUM ANALYZE;"

# Reindex if needed
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "REINDEX DATABASE hp_ti_db;"
```

#### Elasticsearch Issues
```bash
# Check cluster health
curl -X GET "localhost:9200/_cluster/health?pretty"

# Clear cache
curl -X POST "localhost:9200/_cache/clear?pretty"

# Force merge old indices
curl -X POST "localhost:9200/hp_ti_logs-*/_forcemerge?max_num_segments=1"

# Delete old indices (30+ days)
curl -X DELETE "localhost:9200/hp_ti_logs-$(date -d '30 days ago' +%Y.%m.%d)"
```

#### Resource Exhaustion
```bash
# Clean up Docker resources
docker system prune -af --volumes

# Clean up old logs
find /var/log/hp_ti -name "*.log" -mtime +7 -delete

# Clear Redis cache
docker exec hp_ti_redis redis-cli FLUSHDB

# Archive old data
./scripts/archive_old_data.sh --older-than 90
```

### 6. Communication Plan

**Stakeholder Updates**:

**Initial Notification** (within 15 minutes):
```
Subject: [P{level}] HP_TI Incident - {Brief Description}

Incident: {ID}
Severity: P{level}
Start Time: {timestamp}
Impact: {description of impact}
Status: Investigating

We are aware of {issue description} and are currently investigating.
Next update in: 30 minutes

Incident Commander: {name}
```

**Status Updates** (every 30-60 minutes):
```
Subject: [P{level}] HP_TI Incident Update - {Description}

Incident: {ID}
Update #: {number}
Time: {timestamp}

Current Status: {status}
Actions Taken: {list of actions}
Next Steps: {planned actions}
ETA for Resolution: {estimate}

Next update in: {timeframe}
```

**Resolution Notification**:
```
Subject: [RESOLVED] HP_TI Incident - {Description}

Incident: {ID}
Resolution Time: {timestamp}
Total Duration: {duration}

Root Cause: {brief explanation}
Resolution: {what was done}
Preventive Measures: {what will be done to prevent recurrence}

A full post-incident report will be published within 48 hours.
```

### 7. Post-Incident Activities

**Immediate** (within 1 hour of resolution):
- [ ] Verify all services operational
- [ ] Run full health check suite
- [ ] Monitor for 30 minutes
- [ ] Update incident status
- [ ] Thank response team

**Short-term** (within 24 hours):
- [ ] Document incident timeline
- [ ] Collect all relevant logs and metrics
- [ ] Create preliminary root cause analysis
- [ ] Identify immediate action items

**Long-term** (within 48 hours):
- [ ] Conduct post-incident review meeting
- [ ] Create detailed post-mortem document
- [ ] Identify preventive measures
- [ ] Create tickets for improvements
- [ ] Update runbooks and documentation

## Common Incident Scenarios

### Scenario 1: All Honeypot Services Down

**Symptoms**:
- All honeypot_service_up metrics = 0
- No incoming connection logs
- Honeypot container not running

**Resolution**:
```bash
# 1. Check Docker status
docker-compose ps

# 2. Check honeypot logs
docker-compose logs honeypot --tail=200

# 3. Restart honeypot service
docker-compose restart honeypot

# 4. If restart fails, check configuration
docker-compose config

# 5. If config invalid, restore from backup
cp /var/backups/hp_ti/config/config_latest.tar.gz /tmp/
tar -xzf /tmp/config_latest.tar.gz -C /opt/hp_ti/

# 6. Restart services
docker-compose down
docker-compose up -d

# 7. Verify recovery
./deployment/scripts/health_check.sh
```

### Scenario 2: Database Connection Pool Exhausted

**Symptoms**:
- Connection timeout errors in logs
- "FATAL: remaining connection slots are reserved" errors
- Application unable to process events

**Resolution**:
```bash
# 1. Check current connections
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 2. Identify connection hogs
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pid, usename, application_name, client_addr, state, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start
LIMIT 20;"

# 3. Kill idle connections (older than 10 minutes)
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '10 minutes'
  AND pid <> pg_backend_pid();"

# 4. Restart application to reset connection pool
docker-compose restart honeypot

# 5. Increase max_connections if needed (edit postgresql.conf)
# max_connections = 200

# 6. Monitor connection usage
watch "docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \"SELECT count(*) FROM pg_stat_activity;\""
```

### Scenario 3: Elasticsearch Cluster Yellow/Red

**Symptoms**:
- Elasticsearch cluster health not green
- Slow query performance
- Unassigned shards

**Resolution**:
```bash
# 1. Check cluster health
curl -X GET "localhost:9200/_cluster/health?pretty"

# 2. Check unassigned shards
curl -X GET "localhost:9200/_cat/shards?v&h=index,shard,prirep,state,unassigned.reason"

# 3. Check node disk space
curl -X GET "localhost:9200/_cat/nodes?v&h=name,disk.used_percent,heap.percent"

# 4. If disk space issue, delete old indices
curl -X DELETE "localhost:9200/hp_ti_logs-$(date -d '60 days ago' +%Y.%m.%d)"

# 5. Retry shard allocation
curl -X POST "localhost:9200/_cluster/reroute?retry_failed=true"

# 6. If specific index stuck, close and reopen
curl -X POST "localhost:9200/hp_ti_logs-2025.01.01/_close"
curl -X POST "localhost:9200/hp_ti_logs-2025.01.01/_open"

# 7. Monitor recovery
watch "curl -s 'localhost:9200/_cluster/health?pretty'"
```

### Scenario 4: High Memory Usage

**Symptoms**:
- OOMKilled containers
- Swap usage high
- System slow/unresponsive

**Resolution**:
```bash
# 1. Check memory usage
free -h
docker stats --no-stream

# 2. Identify memory hogs
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | sort -k 2 -h

# 3. Restart high-memory containers
docker-compose restart elasticsearch  # Often the culprit

# 4. Clear caches
docker exec hp_ti_redis redis-cli FLUSHDB
curl -X POST "localhost:9200/_cache/clear"

# 5. Adjust JVM heap for Elasticsearch (if needed)
# Edit docker-compose.yml:
# ES_JAVA_OPTS: "-Xms2g -Xmx2g"

# 6. Set memory limits in docker-compose.yml
# mem_limit: 4g
# memswap_limit: 4g

# 7. Monitor memory
watch "free -h; echo '---'; docker stats --no-stream"
```

### Scenario 5: Pipeline Backlog Growing

**Symptoms**:
- pipeline_queue_size metric increasing
- High processing latency
- Events not being enriched

**Resolution**:
```bash
# 1. Check queue sizes
curl -s http://localhost:9091/metrics | grep pipeline_queue_size

# 2. Check processing rates
curl -s http://localhost:9091/metrics | grep pipeline_events_processed_total

# 3. Check for errors in pipeline logs
docker-compose logs pipeline --tail=500 | grep -i "error\|exception"

# 4. Check enrichment API rate limits
docker-compose logs pipeline | grep -i "rate limit\|too many requests"

# 5. Temporarily disable enrichment if needed
# Set ENABLE_ENRICHMENT=false in .env
docker-compose restart pipeline

# 6. Scale up workers (if using worker model)
docker-compose up -d --scale pipeline_worker=4

# 7. Clear backlog by increasing batch size
# Edit config/pipeline.yaml: batch_size: 1000

# 8. Monitor queue drain
watch "curl -s http://localhost:9091/metrics | grep pipeline_queue_size"
```

### Scenario 6: Security Breach Suspected

**Symptoms**:
- Unexpected administrative actions
- Unknown processes or containers
- Unusual outbound network traffic
- Alerts from IDS/IPS

**CRITICAL - Immediate Actions**:
```bash
# 1. ISOLATE THE SYSTEM
# Block all incoming traffic except management
sudo ufw default deny incoming
sudo ufw allow from YOUR_MANAGEMENT_IP to any port 22

# 2. PRESERVE EVIDENCE
# Take memory dump (if tools available)
# Copy all logs before they rotate
mkdir -p /forensics/$(date +%Y%m%d_%H%M%S)
cp -r /var/log/hp_ti /forensics/$(date +%Y%m%d_%H%M%S)/
docker-compose logs > /forensics/$(date +%Y%m%d_%H%M%S)/docker_logs.txt

# 3. CHECK FOR UNAUTHORIZED ACCESS
# Review auth logs
grep -i "accepted\|failed" /var/log/auth.log | tail -100

# 4. CHECK FOR ROOTKITS AND MALWARE
sudo rkhunter --check --skip-keypress
sudo chkrootkit

# 5. CHECK RUNNING PROCESSES
ps aux | grep -v "\[.*\]" | sort -k 3 -r | head -20

# 6. CHECK NETWORK CONNECTIONS
netstat -antp
ss -antp

# 7. CHECK DOCKER CONTAINERS
docker ps -a
docker inspect $(docker ps -q)

# 8. NOTIFY SECURITY TEAM IMMEDIATELY
# DO NOT TAKE FURTHER ACTION WITHOUT SECURITY LEAD APPROVAL
```

**Follow Security Lead Instructions**:
- Preserve all evidence
- Document all actions taken
- Do not modify or delete anything without approval
- Prepare for potential forensic investigation

## Recovery Time Objectives (RTO)

| Component | RTO | Recovery Procedure |
|-----------|-----|-------------------|
| Honeypot Services | 15 minutes | Container restart or rollback |
| Database | 30 minutes | Restore from latest backup |
| Elasticsearch | 1 hour | Snapshot restore |
| Full System | 4 hours | Complete disaster recovery |

## Recovery Point Objectives (RPO)

| Data Type | RPO | Backup Frequency |
|-----------|-----|------------------|
| Database | 1 hour | Continuous WAL archiving |
| Logs | 15 minutes | Real-time streaming |
| Configuration | 24 hours | Daily backup |
| Metrics | 5 minutes | Prometheus retention |

## Escalation Matrix

| Time Elapsed | Action |
|--------------|--------|
| 0 minutes | Technical Lead responds |
| 15 minutes | Incident Commander notified |
| 30 minutes | Management notified (P0/P1) |
| 1 hour | Executive stakeholders notified (P0) |
| 2 hours | External support engaged if needed |

## Post-Incident Report Template

### Incident Summary
- **Incident ID**:
- **Date/Time**:
- **Duration**:
- **Severity**:
- **Impact**:

### Timeline
| Time | Event | Action Taken |
|------|-------|--------------|
|      |       |              |

### Root Cause Analysis
**What Happened**:

**Why It Happened**:

**Contributing Factors**:

### Resolution
**Actions Taken**:

**Verification**:

### Preventive Measures
**Immediate**:
- [ ]

**Short-term** (1-2 weeks):
- [ ]

**Long-term** (1-3 months):
- [ ]

### Lessons Learned
**What Went Well**:

**What Needs Improvement**:

**Action Items**:
1.
2.
3.

### Sign-off
- Incident Commander: _________________ Date: _______
- Technical Lead: _________________ Date: _______
- Security Lead: _________________ Date: _______

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
