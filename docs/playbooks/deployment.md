# HP_TI Deployment Playbook

## Overview

This playbook provides step-by-step procedures for deploying the HP_TI platform to production and staging environments.

## Pre-Deployment Checklist

### Security Review
- [ ] All items in `deployment/security/security_checklist.md` completed
- [ ] Security hardening script executed
- [ ] Vulnerability scans completed (no critical issues)
- [ ] Penetration testing completed (if production)
- [ ] Security sign-off obtained

### Code Review
- [ ] All code changes peer-reviewed
- [ ] Unit tests passing (>80% coverage)
- [ ] Integration tests passing
- [ ] No debug code or print statements in production code
- [ ] No hardcoded credentials or secrets

### Infrastructure Review
- [ ] Server resources adequate (CPU, memory, disk)
- [ ] Network configuration verified
- [ ] Firewall rules configured
- [ ] SSL/TLS certificates valid
- [ ] DNS records configured
- [ ] Backup systems operational

### Configuration Review
- [ ] Environment variables configured
- [ ] Database connection strings correct
- [ ] External API credentials configured
- [ ] Log rotation configured
- [ ] Monitoring and alerting configured

### Documentation Review
- [ ] Deployment documentation up-to-date
- [ ] Runbooks current
- [ ] Configuration documented
- [ ] Architecture diagrams current
- [ ] Change log updated

## Deployment Environments

### Development
- **Purpose**: Active development and testing
- **URL**: http://dev.hp-ti.local:8080
- **Deployment**: Automatic on commit to `develop` branch
- **Data**: Test data only
- **Monitoring**: Basic

### Staging
- **Purpose**: Pre-production testing and validation
- **URL**: https://staging.hp-ti.example.com
- **Deployment**: Manual approval required
- **Data**: Anonymized production data
- **Monitoring**: Full production-like monitoring

### Production
- **Purpose**: Live production system
- **URL**: https://hp-ti.example.com
- **Deployment**: Manual with change approval
- **Data**: Live production data
- **Monitoring**: Comprehensive 24/7 monitoring

## Deployment Types

### 1. Standard Deployment (Rolling Update)

**Use Case**: Regular feature releases, minor updates

**Steps**:

#### 1. Pre-Deployment Preparation
```bash
# 1. Connect to deployment server
ssh hp_ti_admin@production-server

# 2. Navigate to deployment directory
cd /opt/hp_ti

# 3. Verify current version
git describe --tags
docker-compose ps

# 4. Check system health
./deployment/scripts/health_check.sh --pre-deploy

# 5. Create pre-deployment backup
./deployment/scripts/backup.sh
```

#### 2. Deployment Execution
```bash
# 1. Pull latest code
git fetch origin
git checkout tags/v1.2.3  # Replace with actual version

# 2. Review changes
git log --oneline v1.2.2..v1.2.3

# 3. Execute automated deployment
./deployment/scripts/deploy.sh --environment production --version v1.2.3

# This script will:
# - Run pre-deployment health checks
# - Create automatic backup
# - Pull latest Docker images
# - Run database migrations
# - Deploy new version
# - Run post-deployment health checks
# - Automatically rollback if checks fail
```

#### 3. Verification
```bash
# 1. Verify all services running
docker-compose ps

# 2. Check service health
./deployment/scripts/health_check.sh --post-deploy

# 3. Check application logs
docker-compose logs --tail=100 honeypot
docker-compose logs --tail=100 pipeline

# 4. Verify metrics collection
curl -s http://localhost:9090/metrics | grep honeypot_service_up

# 5. Check Grafana dashboards
# Open http://localhost:3000 and verify all dashboards

# 6. Test honeypot services
nc -zv localhost 2222  # SSH honeypot
nc -zv localhost 8080  # HTTP honeypot

# 7. Check database connectivity
docker exec hp_ti_postgres pg_isready -U hp_ti_user

# 8. Verify Elasticsearch
curl -s http://localhost:9200/_cluster/health | jq .
```

#### 4. Post-Deployment Tasks
```bash
# 1. Monitor for 30 minutes
watch -n 30 './deployment/scripts/health_check.sh'

# 2. Review error logs
docker-compose logs --tail=500 | grep -i "error\|critical\|exception"

# 3. Check alert status
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# 4. Update documentation
# - Update CHANGELOG.md
# - Update deployment log
# - Notify stakeholders

# 5. Tag deployment
git tag -a "deployed-prod-$(date +%Y%m%d-%H%M)" -m "Production deployment v1.2.3"
git push origin --tags
```

### 2. Blue-Green Deployment

**Use Case**: Zero-downtime deployments, major version updates

**Prerequisites**:
- Two identical production environments (Blue and Green)
- Load balancer configured
- Database compatible with both versions

**Steps**:

#### Phase 1: Prepare Green Environment
```bash
# 1. Set up Green environment
ssh hp_ti_admin@green-server
cd /opt/hp_ti

# 2. Deploy new version
git checkout tags/v2.0.0
docker-compose pull
docker-compose up -d

# 3. Run database migrations (non-destructive)
docker-compose exec honeypot python scripts/migrate_database.py --dry-run
docker-compose exec honeypot python scripts/migrate_database.py

# 4. Verify Green environment
./deployment/scripts/health_check.sh --post-deploy

# 5. Test Green environment
./tests/smoke_tests.sh http://green-server:8080
```

#### Phase 2: Switch Traffic
```bash
# 1. Update load balancer to route 10% traffic to Green
# (Load balancer specific - example with nginx)
ssh load-balancer
sudo vim /etc/nginx/conf.d/hp_ti.conf
# Adjust upstream weights: blue=90, green=10
sudo nginx -t
sudo systemctl reload nginx

# 2. Monitor Green environment (15-30 minutes)
# - Check error rates
# - Monitor performance
# - Review logs

# 3. Gradually increase Green traffic
# 10% -> 25% -> 50% -> 75% -> 100%

# 4. Switch 100% to Green
# Adjust upstream weights: blue=0, green=100
sudo systemctl reload nginx
```

#### Phase 3: Decommission Blue
```bash
# 1. Monitor Green at 100% for 1 hour

# 2. Keep Blue running for 24 hours as fallback

# 3. After 24 hours, update Blue to new version
ssh hp_ti_admin@blue-server
cd /opt/hp_ti
git checkout tags/v2.0.0
docker-compose down
docker-compose pull
docker-compose up -d

# 4. Now both environments on same version (ready for next deployment)
```

### 3. Canary Deployment

**Use Case**: High-risk changes, testing with subset of users

**Steps**:

#### 1. Deploy Canary Instance
```bash
# 1. Set up canary server
ssh hp_ti_admin@canary-server
cd /opt/hp_ti

# 2. Deploy new version
git checkout tags/v1.3.0
docker-compose up -d

# 3. Configure canary routing (5% of traffic)
# Update load balancer to route 5% to canary
```

#### 2. Monitor Canary
```bash
# Key metrics to monitor:
# - Error rate (should be < 0.1%)
# - Response time (p95 should be within 10% of baseline)
# - Resource usage (CPU, memory)
# - Alert frequency

# Monitoring period: 4-24 hours depending on traffic volume

# If metrics good: proceed to full rollout
# If metrics bad: rollback canary immediately
```

#### 3. Full Rollout
```bash
# Gradually increase canary traffic:
# 5% -> 25% -> 50% -> 100%

# Or proceed with standard deployment to all servers
```

## Database Migrations

### Pre-Migration Checklist
- [ ] Migration tested in staging environment
- [ ] Migration is backward-compatible (for rollback)
- [ ] Database backup completed
- [ ] Migration downtime estimated
- [ ] Stakeholders notified if downtime required

### Migration Execution

#### Non-Destructive Migrations (Preferred)
```bash
# 1. Run migration script
docker-compose exec honeypot python scripts/migrate_database.py

# 2. Verify migration
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\dt"
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\d+ table_name"

# 3. Test backward compatibility
# Deploy old version and verify it still works
```

#### Destructive Migrations (Requires Downtime)
```bash
# 1. Put system in maintenance mode
docker-compose stop honeypot pipeline

# 2. Create backup
./deployment/scripts/backup.sh --database-only

# 3. Run migration
docker-compose exec postgres psql -U hp_ti_user -d hp_ti_db -f /migrations/001_destructive.sql

# 4. Verify migration
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;"

# 5. Start services
docker-compose up -d

# 6. Verify application
./deployment/scripts/health_check.sh --post-deploy
```

## Rollback Procedures

### When to Rollback
- Health checks failing after deployment
- Critical bugs discovered in production
- Performance degradation > 20%
- Data integrity issues
- Security vulnerabilities introduced

### Rollback Execution

#### Automated Rollback (Preferred)
```bash
# The deploy.sh script automatically rolls back if health checks fail
# Manual rollback can be triggered:

./deployment/scripts/rollback.sh

# This will:
# - Stop current services
# - Restore previous version from backup
# - Restore database (if needed)
# - Run health checks
# - Notify team
```

#### Manual Rollback
```bash
# 1. Stop current services
docker-compose down

# 2. Checkout previous version
git checkout tags/v1.2.2  # Previous stable version

# 3. Restore configuration (if changed)
./deployment/scripts/restore.sh --backup 20250115_143000 --config-only

# 4. Restore database (if migrations ran)
./deployment/scripts/restore.sh --backup 20250115_143000 --database-only

# 5. Start services
docker-compose up -d

# 6. Verify rollback
./deployment/scripts/health_check.sh --post-deploy

# 7. Monitor for 30 minutes
watch -n 30 './deployment/scripts/health_check.sh'
```

## Deployment Schedule

### Recommended Deployment Windows

**Production**:
- **Day**: Tuesday or Wednesday (avoid Monday and Friday)
- **Time**: 10:00 AM - 2:00 PM local time (normal business hours)
- **Avoid**: Holidays, weekends, end-of-month, during major events

**Rationale**:
- Staff available for monitoring
- Time to address issues before evening
- Recovery possible before end of business day
- Full team available (not Monday morning or Friday afternoon)

### Emergency Hotfix Deployment
- **Criteria**: Critical security vulnerability or data loss bug
- **Approval**: Security Lead + CTO
- **Process**: Expedited deployment with abbreviated testing
- **Communication**: Immediate notification to all stakeholders

## Deployment Communication

### Pre-Deployment Notification (24 hours before)
```
Subject: HP_TI Deployment Scheduled - [Date] [Time]

Team,

A deployment of HP_TI version [X.Y.Z] is scheduled for:
Date: [Date]
Time: [Start Time] - [End Time]
Duration: [Estimated]
Impact: [None/Minimal/Degraded Performance/Downtime]

Changes:
- [Feature 1]
- [Feature 2]
- [Bug fix 1]

Full changelog: [URL]

Please contact [Name] with any concerns.

Thanks,
[Deployment Lead]
```

### Deployment Start Notification
```
Subject: HP_TI Deployment Starting - [Version]

Deployment of HP_TI v[X.Y.Z] is starting now.

Expected duration: [X minutes]
Monitoring dashboard: [URL]
Status updates: Every 15 minutes

Deployment Team:
- Commander: [Name]
- Technical: [Name]
- Communications: [Name]
```

### Deployment Completion Notification
```
Subject: HP_TI Deployment Complete - [Version]

Deployment of HP_TI v[X.Y.Z] completed successfully.

Start: [Time]
End: [Time]
Duration: [Actual]
Status: Success / Issues Encountered

Post-deployment verification:
- All services: ✓ Running
- Health checks: ✓ Passed
- Monitoring: ✓ Operational

Known Issues: [None / List]

Monitoring will continue for the next 24 hours.

Thanks,
[Deployment Lead]
```

## Monitoring Post-Deployment

### First Hour (Active Monitoring)
```bash
# 1. Watch metrics dashboard (Grafana)
# - Connection rates
# - Error rates
# - Response times
# - Resource utilization

# 2. Monitor logs in real-time
docker-compose logs -f --tail=100 | grep -i "error\|critical\|exception"

# 3. Check alert status every 5 minutes
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# 4. Review specific metrics
curl -s http://localhost:9090/metrics | grep honeypot_connections_total
```

### First 24 Hours (Periodic Checks)
- **Every hour**: Check health checks, review error logs
- **Every 4 hours**: Review metrics dashboards, check resource usage
- **Before end of business**: Full health check and stakeholder update

### First Week (Daily Checks)
- **Daily**: Review daily metrics report
- **Daily**: Check for anomalies in attack patterns
- **Daily**: Review performance metrics
- **Weekly**: Generate and review weekly report

## Troubleshooting Common Deployment Issues

### Issue: Deployment Script Fails
```bash
# Check deployment logs
cat /var/log/hp_ti_deploy_*.log | tail -100

# Verify prerequisites
docker --version
docker-compose --version
git status

# Check disk space
df -h

# Check permissions
ls -la /opt/hp_ti
```

### Issue: Services Won't Start After Deployment
```bash
# Check Docker status
systemctl status docker

# Check service logs
docker-compose logs honeypot --tail=200
docker-compose logs postgres --tail=200

# Check configuration
docker-compose config

# Verify environment variables
docker-compose exec honeypot env | grep HP_TI
```

### Issue: Health Checks Failing
```bash
# Run individual health checks
docker ps | grep hp_ti
docker exec hp_ti_postgres pg_isready -U hp_ti_user
curl -s http://localhost:9200/_cluster/health
docker exec hp_ti_redis redis-cli ping

# Check network connectivity
nc -zv localhost 2222
nc -zv localhost 8080
nc -zv localhost 5432
```

### Issue: Database Migration Failed
```bash
# Check migration logs
docker-compose logs postgres | grep -i "migration\|error"

# Check database schema version
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 5;"

# Rollback database
./deployment/scripts/restore.sh --backup TIMESTAMP --database-only

# Rerun migration manually
docker-compose exec postgres psql -U hp_ti_user -d hp_ti_db -f /migrations/XXX_migration.sql
```

## Deployment Metrics

Track and review these metrics for each deployment:

| Metric | Target | Actual | Notes |
|--------|--------|--------|-------|
| Deployment Duration | < 30 minutes | | |
| Downtime | 0 minutes | | |
| Failed Deployments | 0 | | |
| Rollbacks | 0 | | |
| Post-Deployment Issues | 0 | | |
| Time to Resolution | < 1 hour | | |

## Continuous Improvement

### Post-Deployment Review Questions
1. Did the deployment go as planned?
2. Were there any unexpected issues?
3. How effective was the communication?
4. Did monitoring catch issues promptly?
5. What can be improved for next time?

### Deployment Process Improvements
- Automate manual steps
- Improve health checks
- Enhance monitoring
- Update documentation
- Add automated tests
- Refine rollback procedures

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
**Owner**: DevOps Team
