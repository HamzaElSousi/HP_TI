# HP_TI Rollback Playbook

## Overview

This playbook provides procedures for rolling back HP_TI deployments when issues are encountered in production.

## Rollback Decision Criteria

### When to Rollback

Execute rollback when:
- **Critical bugs** discovered affecting core functionality
- **Health checks failing** consistently after deployment
- **Performance degradation** > 20% from baseline
- **Data integrity issues** detected
- **Security vulnerabilities** introduced
- **Cascading failures** affecting multiple components
- **Recovery impossible** within 30 minutes

### When NOT to Rollback

Consider alternatives when:
- **Minor cosmetic issues** that don't affect functionality
- **Configuration problems** that can be fixed without code changes
- **Single component failures** that can be restarted
- **Performance issues** that can be tuned
- **Issue affects < 5%** of users (consider canary rollback)

## Rollback Types

### 1. Automated Rollback

The deployment script includes automatic rollback on health check failure.

**Trigger**: Health checks fail post-deployment

**Process**:
```bash
# Automatic rollback is triggered by deploy.sh when health checks fail
# To view rollback logs:
tail -f /var/log/hp_ti_deploy_*.log

# Rollback will:
# 1. Stop current version
# 2. Restore previous version from backup
# 3. Restore database if needed
# 4. Run health checks
# 5. Send notifications
```

### 2. Manual Rollback

**Trigger**: Manual decision to rollback

**Process**:
```bash
# Execute rollback script
./deployment/scripts/rollback.sh

# Or specify specific backup:
./deployment/scripts/rollback.sh --backup hp_ti_20250115_143000

# Or restore from latest backup:
./deployment/scripts/rollback.sh --latest
```

### 3. Partial Rollback

**Trigger**: Only specific component needs rollback

#### Rollback Single Service
```bash
# 1. Identify problematic service
docker-compose ps

# 2. Stop the service
docker-compose stop honeypot

# 3. Restore previous image
docker pull hp_ti/honeypot:v1.2.2  # Previous version
docker tag hp_ti/honeypot:v1.2.2 hp_ti/honeypot:latest

# 4. Start service
docker-compose up -d honeypot

# 5. Verify
docker-compose ps
./deployment/scripts/health_check.sh
```

#### Rollback Configuration Only
```bash
# Restore configuration from backup
./deployment/scripts/restore.sh --backup 20250115_143000 --config-only

# Restart services to apply
docker-compose restart
```

#### Rollback Database Only
```bash
# Restore database from backup
./deployment/scripts/restore.sh --backup 20250115_143000 --database-only

# Verify database version
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 1;"
```

## Rollback Procedures by Scenario

### Scenario 1: Application Code Issues

**Symptoms**:
- Application crashes or errors
- Functional bugs
- Logic errors

**Rollback Steps**:
```bash
# 1. Declare rollback decision
echo "ROLLBACK INITIATED: Application code issues" | tee -a /var/log/hp_ti_rollback.log

# 2. Stop current version
docker-compose down

# 3. Checkout previous stable version
cd /opt/hp_ti
git fetch origin
git checkout tags/v1.2.2  # Replace with last known good version

# 4. Start services with previous version
docker-compose up -d

# 5. Verify services
./deployment/scripts/health_check.sh --post-deploy

# 6. Monitor for 15 minutes
watch -n 30 './deployment/scripts/health_check.sh'

# 7. Verify functionality
./tests/smoke_tests.sh

# 8. Document rollback
echo "ROLLBACK COMPLETED: $(date)" | tee -a /var/log/hp_ti_rollback.log
```

### Scenario 2: Database Migration Issues

**Symptoms**:
- Database errors
- Schema mismatch
- Data corruption
- Migration failed

**Rollback Steps**:
```bash
# 1. Identify backup timestamp (before migration)
ls -lh /var/backups/hp_ti/database/

# 2. Stop application to prevent writes
docker-compose stop honeypot pipeline

# 3. Terminate active connections
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE datname = 'hp_ti_db' AND pid <> pg_backend_pid();"

# 4. Restore database from pre-migration backup
./deployment/scripts/restore.sh --backup 20250115_143000 --database-only

# 5. Verify database restore
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\dt"
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 5;"

# 6. Rollback application code
git checkout tags/v1.2.2

# 7. Start services
docker-compose up -d

# 8. Verify
./deployment/scripts/health_check.sh --post-deploy
```

**Alternative: Point-in-Time Recovery (if WAL archiving enabled)**:
```bash
# Restore to specific point in time before migration
docker exec hp_ti_postgres pg_basebackup -D /var/lib/postgresql/backup -F tar -z -P

# Use pg_restore with --target-time option
# This is advanced - consult DBA if needed
```

### Scenario 3: Configuration Issues

**Symptoms**:
- Services won't start
- Connection failures
- Invalid configuration errors

**Rollback Steps**:
```bash
# 1. Restore configuration from backup
./deployment/scripts/restore.sh --backup 20250115_143000 --config-only

# 2. Verify configuration
docker-compose config

# 3. Check environment variables
cat /opt/hp_ti/.env
# Verify critical variables are set correctly

# 4. Restart services
docker-compose restart

# 5. Verify
./deployment/scripts/health_check.sh --post-deploy
```

### Scenario 4: Performance Degradation

**Symptoms**:
- High latency (> 2x baseline)
- High resource usage
- Slow queries
- Timeout errors

**Immediate Mitigation**:
```bash
# 1. Scale down traffic if possible
# Adjust load balancer weights

# 2. Clear caches
docker exec hp_ti_redis redis-cli FLUSHDB
curl -X POST "localhost:9200/_cache/clear"

# 3. Restart services
docker-compose restart

# 4. If no improvement in 10 minutes, proceed with rollback
```

**Rollback Decision**:
```bash
# If performance doesn't improve, rollback
./deployment/scripts/rollback.sh

# Monitor performance post-rollback
watch -n 10 'curl -s http://localhost:9090/metrics | grep -E "honeypot_request_duration|pipeline_processing_latency"'
```

### Scenario 5: Docker Image Issues

**Symptoms**:
- Container crashes immediately
- Image pull failures
- Image corruption

**Rollback Steps**:
```bash
# 1. Stop affected services
docker-compose stop honeypot

# 2. Remove corrupted images
docker rmi hp_ti/honeypot:v1.2.3

# 3. Pull previous stable image
docker pull hp_ti/honeypot:v1.2.2
docker tag hp_ti/honeypot:v1.2.2 hp_ti/honeypot:latest

# 4. Update docker-compose.yml to use specific tag
# Change: image: hp_ti/honeypot:latest
# To:     image: hp_ti/honeypot:v1.2.2

# 5. Start service
docker-compose up -d honeypot

# 6. Verify
docker-compose ps
docker-compose logs honeypot --tail=100
```

### Scenario 6: Elasticsearch Index Issues

**Symptoms**:
- Index corruption
- Mapping conflicts
- Query failures

**Rollback Steps**:
```bash
# 1. Identify affected indices
curl -X GET "localhost:9200/_cat/indices?v"

# 2. Close affected indices
curl -X POST "localhost:9200/hp_ti_logs-2025.01.15/_close"

# 3. Restore from snapshot
SNAPSHOT_NAME="snapshot_20250115_143000"
curl -X POST "localhost:9200/_snapshot/hp_ti_backups/${SNAPSHOT_NAME}/_restore" \
  -H 'Content-Type: application/json' \
  -d '{
    "indices": "hp_ti_logs-2025.01.15",
    "ignore_unavailable": true,
    "include_global_state": false
  }'

# 4. Wait for restore to complete
watch -n 5 'curl -s "localhost:9200/_cat/recovery?v&h=index,stage,type,percent"'

# 5. Reopen index
curl -X POST "localhost:9200/hp_ti_logs-2025.01.15/_open"

# 6. Verify
curl -X GET "localhost:9200/hp_ti_logs-2025.01.15/_search?size=10"
```

## Rollback Communication

### Rollback Decision Announcement
```
Subject: [URGENT] HP_TI Rollback Initiated - v[X.Y.Z]

Team,

A rollback of HP_TI v[X.Y.Z] has been initiated.

Reason: [Brief description]
Severity: [Critical/High/Medium]
Impact: [Description]
Rolling back to: v[Previous Version]

Expected rollback duration: [X minutes]
Rollback started: [Time]

Rollback Commander: [Name]
Technical Lead: [Name]

Next update in: 15 minutes
```

### Rollback Completion Announcement
```
Subject: [RESOLVED] HP_TI Rollback Complete - Now on v[X.Y.Z]

Team,

HP_TI rollback completed successfully.

Rolled back from: v[Failed Version]
Rolled back to: v[Stable Version]
Rollback duration: [Actual time]

Verification:
- All services: ✓ Running
- Health checks: ✓ Passed
- Functionality: ✓ Verified

Root Cause: [Brief explanation]
Next Steps:
1. Full investigation to be completed within 24 hours
2. Fix to be developed and tested
3. Post-incident report within 48 hours

System is stable and monitoring continues.

Thanks,
[Rollback Commander]
```

## Post-Rollback Procedures

### Immediate (Within 1 Hour)
```bash
# 1. Verify system stability
./deployment/scripts/health_check.sh
watch -n 60 './deployment/scripts/health_check.sh'

# 2. Monitor error rates
docker-compose logs --tail=500 | grep -i "error\|critical"

# 3. Check metrics
# Review Grafana dashboards for anomalies

# 4. Verify data integrity
# Run data consistency checks
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM honeypot_events WHERE created_at > NOW() - INTERVAL '1 hour';"

# 5. Document rollback
cat > /tmp/rollback_report_$(date +%Y%m%d_%H%M%S).txt <<EOF
Rollback Summary
================
Date: $(date)
Rolled back from: v[X.Y.Z]
Rolled back to: v[Previous]
Reason: [Reason]
Duration: [Duration]
Issues encountered: [None/List]
System status: [Stable/Unstable]
EOF
```

### Short-term (Within 24 Hours)
- [ ] Conduct rollback post-mortem meeting
- [ ] Document root cause of deployment failure
- [ ] Identify what went wrong in testing
- [ ] Create tickets for fixes
- [ ] Update deployment checklist if needed
- [ ] Notify all stakeholders

### Long-term (Within 1 Week)
- [ ] Implement fixes for root cause
- [ ] Enhance testing to catch issue
- [ ] Update rollback procedures if needed
- [ ] Add monitoring/alerts to prevent recurrence
- [ ] Re-deploy with fixes to staging
- [ ] Schedule new production deployment

## Rollback Testing

### Regular Rollback Drills

**Frequency**: Quarterly

**Procedure**:
```bash
# 1. Schedule drill during low-traffic period
# 2. Announce drill to team (not to users)
# 3. Execute standard deployment
# 4. Immediately execute rollback
# 5. Time the rollback process
# 6. Verify system recovery
# 7. Document lessons learned
# 8. Update procedures if needed
```

**Success Criteria**:
- Rollback completes in < 15 minutes
- All services return to healthy state
- No data loss
- Team executes procedures correctly

## Rollback Decision Matrix

| Issue Severity | Response Time | Decision Maker | Rollback Type |
|----------------|---------------|----------------|---------------|
| **P0 - Critical** | Immediate | Incident Commander | Immediate rollback |
| **P1 - High** | < 15 minutes | Technical Lead + IC | Rollback if no fix in 30min |
| **P2 - Medium** | < 1 hour | Technical Lead | Rollback vs. forward fix |
| **P3 - Low** | < 4 hours | Team decision | Forward fix preferred |

## Rollback Metrics

Track these metrics for each rollback:

| Metric | Target | Actual |
|--------|--------|--------|
| Detection Time | < 5 minutes | |
| Decision Time | < 10 minutes | |
| Rollback Duration | < 15 minutes | |
| Time to Stability | < 30 minutes | |
| Data Loss | 0 records | |
| Downtime | < 5 minutes | |

## Prevention Strategies

### Better Testing
- Enhance staging environment to mirror production
- Add more integration tests
- Implement automated smoke tests
- Add performance regression tests
- Load test before production deployment

### Better Deployment Process
- Use canary deployments for risky changes
- Implement feature flags for new features
- Deploy during low-traffic periods
- Have rollback plan before deploying
- Practice rollback procedures

### Better Monitoring
- Add pre-deployment baseline capture
- Implement deployment markers in monitoring
- Add automated anomaly detection
- Alert on deployment-related metrics
- Track deployment success rate

## Troubleshooting Rollback Issues

### Issue: Rollback Script Fails
```bash
# Check rollback logs
cat /var/log/hp_ti_rollback_*.log

# Manually execute rollback steps
cd /opt/hp_ti
git checkout tags/v[previous-version]
docker-compose down
docker-compose up -d

# Restore from backup if needed
./deployment/scripts/restore.sh --backup [timestamp]
```

### Issue: Database Rollback Fails
```bash
# Check backup integrity
ls -lh /var/backups/hp_ti/database/
sha256sum -c /var/backups/hp_ti/database/postgres_*.sha256

# Manual database restore
zcat /var/backups/hp_ti/database/postgres_[timestamp].sql.gz | \
  docker exec -i hp_ti_postgres psql -U hp_ti_user

# Verify restore
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\dt"
```

### Issue: Services Won't Start After Rollback
```bash
# Check Docker logs
docker-compose logs --tail=200

# Check system resources
df -h
free -h
docker stats --no-stream

# Check configuration
docker-compose config

# Restart Docker daemon
sudo systemctl restart docker
docker-compose up -d
```

## Emergency Rollback Contact List

| Role | Name | Phone | Email | Escalation |
|------|------|-------|-------|------------|
| On-Call Engineer | [Name] | [Phone] | [Email] | Primary |
| Technical Lead | [Name] | [Phone] | [Email] | +15 min |
| Engineering Manager | [Name] | [Phone] | [Email] | +30 min |
| CTO | [Name] | [Phone] | [Email] | +1 hour |

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
**Owner**: DevOps Team
