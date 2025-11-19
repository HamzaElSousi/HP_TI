# HP_TI Disaster Recovery Playbook

## Overview

This playbook provides procedures for recovering the HP_TI platform from catastrophic failures including complete server loss, data center outages, and critical data corruption.

## Recovery Objectives

### Recovery Time Objective (RTO)

| Scenario | RTO Target | Maximum Acceptable |
|----------|------------|-------------------|
| **Single Service Failure** | 15 minutes | 30 minutes |
| **Database Failure** | 30 minutes | 1 hour |
| **Complete Server Failure** | 2 hours | 4 hours |
| **Data Center Outage** | 4 hours | 8 hours |
| **Regional Disaster** | 24 hours | 48 hours |

### Recovery Point Objective (RPO)

| Data Type | RPO Target | Backup Method |
|-----------|-----------|---------------|
| **Database** | 15 minutes | Continuous WAL archiving |
| **Honeypot Logs** | 5 minutes | Real-time Elasticsearch replication |
| **Configuration** | 24 hours | Daily backups |
| **System State** | 1 hour | Automated snapshots |

## Disaster Scenarios

### Scenario 1: Single Server Failure

**Description**: Production server hardware failure or OS corruption

**Impact**: Complete service outage

**Recovery Procedure**:

#### Phase 1: Assessment (0-10 minutes)
```bash
# From backup/monitoring server:

# 1. Verify server is unreachable
ping production-server
ssh production-server  # Will fail

# 2. Check monitoring dashboards
# All metrics flatlined = server down

# 3. Attempt remote recovery
# IPMI/iDRAC/iLO console access
# Attempt reboot via remote management

# 4. If recovery impossible, proceed with disaster recovery
```

#### Phase 2: Provision New Server (10-30 minutes)
```bash
# Option A: Cloud (AWS/Azure/GCP)
# Launch new EC2/VM instance from pre-configured AMI/image

# Option B: Physical Hardware
# Deploy spare server with base OS

# 1. Launch new server
aws ec2 run-instances \
  --image-id ami-hp-ti-base \
  --instance-type t3.xlarge \
  --key-name hp-ti-key \
  --security-group-ids sg-hp-ti \
  --subnet-id subnet-hp-ti

# 2. Wait for server to be ready
aws ec2 wait instance-running --instance-ids i-xxxxx

# 3. Get new server IP
NEW_SERVER_IP=$(aws ec2 describe-instances \
  --instance-ids i-xxxxx \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

# 4. Update DNS (if applicable)
# Point hp-ti.example.com to NEW_SERVER_IP
```

#### Phase 3: Restore System (30-90 minutes)
```bash
# 1. SSH to new server
ssh -i hp-ti-key.pem ubuntu@$NEW_SERVER_IP

# 2. Install dependencies
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git

# 3. Clone repository
cd /opt
sudo git clone https://github.com/org/HP_TI.git hp_ti
cd hp_ti
sudo git checkout tags/v1.2.3  # Last known good version

# 4. Restore configuration from backup
# Download latest backup from S3/backup server
aws s3 cp s3://hp-ti-backups/config/config_latest.tar.gz /tmp/
sudo tar -xzf /tmp/config_latest.tar.gz -C /opt/hp_ti/

# 5. Restore environment file
aws s3 cp s3://hp-ti-backups/env/.env /opt/hp_ti/.env
sudo chmod 600 /opt/hp_ti/.env

# 6. Start infrastructure services first
sudo docker-compose up -d postgres redis elasticsearch

# 7. Wait for databases to be ready (2-3 minutes)
sleep 180

# 8. Restore database from latest backup
LATEST_BACKUP=$(aws s3 ls s3://hp-ti-backups/database/ | sort | tail -1 | awk '{print $4}')
aws s3 cp s3://hp-ti-backups/database/$LATEST_BACKUP /tmp/
sudo zcat /tmp/$LATEST_BACKUP | \
  docker exec -i hp_ti_postgres psql -U hp_ti_user

# 9. Restore Elasticsearch indices from snapshot
# (If snapshot repository configured)
sudo docker exec hp_ti_elasticsearch \
  curl -X POST "localhost:9200/_snapshot/hp_ti_backups/snapshot_latest/_restore"

# 10. Start application services
sudo docker-compose up -d honeypot pipeline

# 11. Run health checks
./deployment/scripts/health_check.sh --post-deploy
```

#### Phase 4: Verification (90-120 minutes)
```bash
# 1. Verify all services running
docker-compose ps

# 2. Check service health
./deployment/scripts/health_check.sh

# 3. Verify data recovery
# Check record counts
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM honeypot_events;"

# 4. Test honeypot services
nc -zv localhost 2222
nc -zv localhost 8080

# 5. Check Elasticsearch data
curl -s "localhost:9200/hp_ti_logs-*/_count" | jq .

# 6. Verify metrics collection
curl -s http://localhost:9090/metrics | head -20

# 7. Check recent logs
docker-compose logs --tail=100 | grep -i "error\|critical"

# 8. Monitor for 30 minutes
watch -n 30 './deployment/scripts/health_check.sh'
```

### Scenario 2: Database Corruption/Loss

**Description**: Critical database corruption or complete database loss

**Impact**: Data loss, application unable to function

**Recovery Procedure**:

#### Option A: Restore from Latest Backup
```bash
# 1. Stop application to prevent writes
docker-compose stop honeypot pipeline

# 2. Identify latest valid backup
ls -lth /var/backups/hp_ti/database/
# Or from S3:
aws s3 ls s3://hp-ti-backups/database/ | sort | tail -5

# 3. Verify backup integrity
BACKUP_FILE="postgres_20250115_143000.sql.gz"
sha256sum -c ${BACKUP_FILE}.sha256

# 4. Drop corrupted database (DESTRUCTIVE)
docker exec hp_ti_postgres psql -U hp_ti_user -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'hp_ti_db';"
docker exec hp_ti_postgres psql -U hp_ti_user -c "DROP DATABASE hp_ti_db;"
docker exec hp_ti_postgres psql -U hp_ti_user -c "CREATE DATABASE hp_ti_db;"

# 5. Restore from backup
zcat /var/backups/hp_ti/database/${BACKUP_FILE} | \
  docker exec -i hp_ti_postgres psql -U hp_ti_user -d hp_ti_db

# 6. Verify restore
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\dt"
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM honeypot_events;"

# 7. Start application
docker-compose up -d honeypot pipeline

# 8. Monitor for issues
./deployment/scripts/health_check.sh
```

#### Option B: Point-in-Time Recovery (if WAL archiving enabled)
```bash
# 1. Stop PostgreSQL
docker-compose stop postgres

# 2. Restore base backup
# (Restore from most recent base backup before corruption)

# 3. Restore WAL files
# Copy WAL files from archive to pg_wal directory

# 4. Configure recovery
cat > /var/lib/postgresql/data/recovery.conf <<EOF
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '2025-01-15 14:30:00'
EOF

# 5. Start PostgreSQL in recovery mode
docker-compose up -d postgres

# 6. Monitor recovery
docker exec hp_ti_postgres tail -f /var/lib/postgresql/data/log/postgresql.log

# 7. After recovery, promote to primary
docker exec hp_ti_postgres pg_ctl promote

# 8. Start application
docker-compose up -d honeypot pipeline
```

### Scenario 3: Complete Data Center Outage

**Description**: Entire data center offline (power, network, natural disaster)

**Impact**: Complete service outage, requires failover to secondary site

**Recovery Procedure**:

#### Prerequisites
- Secondary data center with standby infrastructure
- Regular backup replication to secondary site
- DNS/Load balancer capable of failover
- Up-to-date documentation and credentials

#### Phase 1: Activate Secondary Site
```bash
# 1. Declare disaster and activate DR plan
# Notify team, stakeholders

# 2. Connect to secondary site
ssh dr-admin@secondary-site

# 3. Verify secondary site infrastructure
cd /opt/hp_ti
./deployment/scripts/health_check.sh --pre-deploy

# 4. Restore latest data from replicated backups
# Backups should already be replicated to secondary site
LATEST_DB_BACKUP=$(ls -t /var/backups/hp_ti/database/*.sql.gz | head -1)

# 5. Start infrastructure services
docker-compose up -d postgres redis elasticsearch

# 6. Restore database
sleep 120  # Wait for PostgreSQL to be ready
zcat $LATEST_DB_BACKUP | docker exec -i hp_ti_postgres psql -U hp_ti_user -d hp_ti_db

# 7. Start application services
docker-compose up -d honeypot pipeline

# 8. Verify all services
./deployment/scripts/health_check.sh --post-deploy
```

#### Phase 2: Update DNS/Traffic Routing
```bash
# 1. Update DNS to point to secondary site
# A record: hp-ti.example.com -> secondary-site-ip
# Reduce TTL if possible to speed propagation

# 2. Or update load balancer
# Remove primary site from load balancer pool
# Add secondary site to load balancer pool

# 3. Verify traffic routing
# Monitor connection logs to confirm traffic arriving
docker-compose logs -f honeypot | grep "New connection"
```

#### Phase 3: Monitor and Communicate
```bash
# 1. Monitor secondary site closely
watch -n 30 './deployment/scripts/health_check.sh'

# 2. Send communication to stakeholders
# "Primary site down, failed over to secondary site"
# "Expected data loss: [X minutes based on RPO]"
# "Service restoration time: [timestamp]"

# 3. Begin assessment of primary site damage
# Coordinate with data center team
# Estimate recovery timeline
```

#### Phase 4: Primary Site Recovery (When Available)
```bash
# When primary site is available again:

# 1. Rebuild primary site from secondary backups
# Or repair primary site infrastructure

# 2. Sync data from secondary to primary
# Take backup from secondary site
docker exec hp_ti_postgres pg_dumpall -U hp_ti_user | gzip > /tmp/secondary_sync.sql.gz

# Transfer to primary site
scp /tmp/secondary_sync.sql.gz primary-site:/tmp/

# Restore on primary site
ssh primary-site
zcat /tmp/secondary_sync.sql.gz | docker exec -i hp_ti_postgres psql -U hp_ti_user

# 3. Verify primary site
./deployment/scripts/health_check.sh

# 4. Failback to primary site
# Update DNS/load balancer to route traffic back to primary
# Monitor closely

# 5. Resume normal operations
# Secondary site returns to standby mode
```

### Scenario 4: Ransomware/Security Breach

**Description**: System compromised, data encrypted or corrupted maliciously

**Impact**: Potential data loss, system integrity compromised

**Recovery Procedure**:

#### Phase 1: Containment (IMMEDIATE)
```bash
# 1. ISOLATE THE SYSTEM IMMEDIATELY
# Disconnect from network
sudo ufw default deny incoming
sudo ufw default deny outgoing
sudo ufw allow from MANAGEMENT_IP to any port 22

# 2. DO NOT SHUT DOWN (preserves memory for forensics)
# Keep system running for investigation

# 3. PRESERVE EVIDENCE
# Take memory dump if tools available
# Copy all logs to secure location
mkdir -p /forensics/$(date +%Y%m%d_%H%M%S)
cp -r /var/log/* /forensics/$(date +%Y%m%d_%H%M%S)/
docker-compose logs > /forensics/$(date +%Y%m%d_%H%M%S)/docker_logs.txt

# 4. NOTIFY SECURITY TEAM IMMEDIATELY
# DO NOT PROCEED WITHOUT SECURITY TEAM APPROVAL
```

#### Phase 2: Assessment (Security Team Led)
```bash
# Security team will:
# - Analyze attack vector
# - Determine extent of compromise
# - Collect forensic evidence
# - Determine if data is encrypted
# - Check for backdoors/persistence mechanisms

# 5. Document everything
# - Initial detection time
# - Actions taken
# - Systems affected
# - Data affected
```

#### Phase 3: Recovery (After Security Clearance)
```bash
# 1. If system compromised beyond recovery, rebuild from scratch
# Use clean OS installation
# Follow Scenario 1: Single Server Failure

# 2. Restore from backups BEFORE infection
# Identify last clean backup
# Verify backup integrity
# Restore using disaster recovery procedures

# 3. Restore from clean backup
# Identify backup from before compromise
CLEAN_BACKUP="postgres_20250114_120000.sql.gz"  # Day before compromise
# Follow standard restore procedures

# 4. Scan restored data for malware
# Run antivirus scans
# Check for webshells, backdoors
# Verify integrity of restored files

# 5. Harden system before going live
./deployment/security/hardening_script.sh --production

# 6. Implement additional security controls
# - Change all passwords
# - Rotate all API keys
# - Enable 2FA
# - Add additional monitoring
# - Implement stricter firewall rules

# 7. Gradual restoration
# Restore services one at a time
# Monitor closely for signs of re-infection
```

### Scenario 5: Cloud Provider Outage

**Description**: AWS/Azure/GCP region outage

**Impact**: All cloud resources unavailable

**Recovery Procedure**:

#### Multi-Region Setup (Ideal)
```bash
# If multi-region deployment configured:

# 1. Activate alternate region
# Traffic should automatically fail over via Route53/Traffic Manager

# 2. Verify alternate region health
aws ec2 describe-instances --region us-west-2 --filters "Name=tag:Name,Values=hp-ti-*"

# 3. Monitor failover
# Check DNS propagation
# Verify traffic routing
```

#### Single Region Recovery
```bash
# If single region:

# 1. Monitor cloud provider status
# Check status page for ETA

# 2. If outage extended (>4 hours), deploy to alternate region

# 3. Provision infrastructure in alternate region
# Use Infrastructure-as-Code (Terraform)
cd /path/to/terraform
terraform init
terraform workspace select us-west-2
terraform apply

# 4. Restore data from S3/backup
# S3 is globally replicated, should be available
aws s3 cp s3://hp-ti-backups/database/latest.sql.gz /tmp/ --region us-west-2

# 5. Deploy application
# Follow standard deployment procedures

# 6. Update DNS
# Point to new region
```

## Backup Strategy

### Backup Types

#### 1. Database Backups
```bash
# Full backup (daily)
./deployment/scripts/backup.sh --database-only

# Continuous WAL archiving (for PITR)
# Configured in postgresql.conf:
# wal_level = replica
# archive_mode = on
# archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
```

#### 2. Configuration Backups
```bash
# Daily configuration backup
./deployment/scripts/backup.sh --config-only

# Critical files backed up:
# - /opt/hp_ti/config/*
# - /opt/hp_ti/.env
# - /opt/hp_ti/docker-compose.yml
```

#### 3. Log Backups
```bash
# Real-time log shipping to Elasticsearch
# Elasticsearch snapshots (daily)
./deployment/scripts/backup.sh --elasticsearch-only
```

### Backup Storage Locations

**Primary**: Local server `/var/backups/hp_ti/`
- 7-day retention
- Fast recovery

**Secondary**: S3/Cloud Storage `s3://hp-ti-backups/`
- 90-day retention
- Off-site protection
- Cross-region replication

**Tertiary**: Tape/Cold Storage (for compliance)
- 7-year retention
- Annual backups

### Backup Verification

**Automated Verification** (daily):
```bash
# Verify checksums
./deployment/scripts/backup.sh  # Creates checksums automatically
sha256sum -c /var/backups/hp_ti/database/*.sha256

# Test restore (dry-run)
./deployment/scripts/restore.sh --backup latest --dry-run
```

**Manual Verification** (monthly):
```bash
# Full restore test to separate environment
# 1. Spin up test environment
# 2. Restore from production backups
# 3. Verify data integrity
# 4. Test application functionality
# 5. Document results
```

## Disaster Recovery Testing

### Test Schedule

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| **Backup Restore** | Monthly | Restore single service |
| **Server Failover** | Quarterly | Rebuild single server |
| **DR Site Activation** | Semi-annually | Full site failover |
| **Tabletop Exercise** | Quarterly | Team coordination |
| **Full DR Drill** | Annually | Complete disaster scenario |

### DR Drill Procedure

```bash
# 1. Schedule drill (non-production hours)
# 2. Announce drill to team
# 3. Simulate disaster scenario
# 4. Execute recovery procedures
# 5. Time each phase
# 6. Document issues encountered
# 7. Update procedures
# 8. Conduct post-drill review
```

## Emergency Contacts

### Disaster Recovery Team

| Role | Name | Primary Phone | Secondary | Email |
|------|------|---------------|-----------|-------|
| **DR Coordinator** | [Name] | [Phone] | [Alt Phone] | [Email] |
| **Technical Lead** | [Name] | [Phone] | [Alt Phone] | [Email] |
| **DBA** | [Name] | [Phone] | [Alt Phone] | [Email] |
| **Infrastructure** | [Name] | [Phone] | [Alt Phone] | [Email] |
| **Security Lead** | [Name] | [Phone] | [Alt Phone] | [Email] |

### Vendor Contacts

| Vendor | Support Phone | Account Number | URL |
|--------|---------------|----------------|-----|
| **Cloud Provider** | [Phone] | [Account #] | [Support URL] |
| **Data Center** | [Phone] | [Account #] | [Support URL] |
| **Backup Service** | [Phone] | [Account #] | [Support URL] |
| **DNS Provider** | [Phone] | [Account #] | [Support URL] |

## Communication Plan

### Stakeholder Notification

**Disaster Declaration**:
```
Subject: [DISASTER] HP_TI Disaster Recovery Activated

DISASTER DECLARATION

Date/Time: [Timestamp]
Disaster Type: [Server Failure/Data Center Outage/etc]
Impact: [Complete service outage]
Expected Downtime: [X hours]

Disaster Recovery has been activated.
DR Coordinator: [Name] - [Phone]

Regular updates will be provided every 30 minutes.

Next update: [Time]
```

**Recovery Progress Updates**:
```
Subject: [DR UPDATE #X] HP_TI Disaster Recovery Progress

DR Update #X - [Timestamp]

Progress:
- Phase 1 (Assessment): ✓ Complete
- Phase 2 (Provisioning): ⏳ In Progress (60%)
- Phase 3 (Restoration): ⏸ Pending
- Phase 4 (Verification): ⏸ Pending

Current Status: Restoring database from backup
ETA for Service Restoration: [Time]

Next update in: 30 minutes
```

**Recovery Completion**:
```
Subject: [RESOLVED] HP_TI Disaster Recovery Complete

Disaster Recovery Completed Successfully

Disaster Start: [Time]
Recovery Complete: [Time]
Total Downtime: [Duration]

All services restored and verified.
Data loss: [None/X minutes of data]

Full post-incident report will be provided within 48 hours.

System is being monitored closely. Thank you for your patience.
```

## Recovery Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Detection Time** | < 5 minutes | Time from failure to declaration |
| **DR Activation Time** | < 30 minutes | Time from declaration to start of recovery |
| **Database Restore Time** | < 1 hour | Time to restore database |
| **Full System Recovery** | < 4 hours | Time to complete service restoration |
| **Data Loss** | < 15 minutes | Amount of data lost (based on RPO) |

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
**Owner**: Infrastructure Team
