# HP_TI Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the HP_TI (Honeypot & Threat Intelligence) platform to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Security Hardening](#security-hardening)
4. [Application Deployment](#application-deployment)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring Setup](#monitoring-setup)
7. [Backup Configuration](#backup-configuration)
8. [Operational Handoff](#operational-handoff)

## Prerequisites

### Hardware Requirements

**Minimum Production Configuration**:

| Component | Specification |
|-----------|--------------|
| **CPU** | 8 cores (16 vCPU recommended) |
| **Memory** | 32 GB RAM (64 GB recommended) |
| **Storage** | 500 GB SSD (1 TB recommended) |
| **Network** | 1 Gbps connection |
| **OS** | Ubuntu 22.04 LTS or RHEL 8+ |

**Recommended Production Configuration**:

| Component | Specification |
|-----------|--------------|
| **Application Server** | 8 cores, 32 GB RAM, 200 GB SSD |
| **Database Server** | 8 cores, 32 GB RAM, 500 GB SSD (IOPS optimized) |
| **Elasticsearch Server** | 16 cores, 64 GB RAM, 1 TB SSD |
| **Load Balancer** | 4 cores, 8 GB RAM, 100 GB SSD |

### Software Requirements

- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Git**: Version 2.30+
- **Python**: 3.11+ (for deployment scripts)
- **OpenSSL**: 1.1.1+
- **curl**: 7.68+

### Network Requirements

- **Incoming Ports** (Firewall Rules):
  - 22/tcp - SSH (management only, restrict to admin IPs)
  - 2222/tcp - SSH Honeypot (public)
  - 8080/tcp - HTTP Honeypot (public)
  - 8443/tcp - HTTPS Honeypot (public)
  - 2323/tcp - Telnet Honeypot (public)
  - 2121/tcp - FTP Honeypot (public)

- **Internal Ports** (Private network only):
  - 5432/tcp - PostgreSQL
  - 9200/tcp - Elasticsearch
  - 6379/tcp - Redis
  - 9090/tcp - Prometheus Metrics
  - 3000/tcp - Grafana (optional, if exposed)

- **Outgoing Ports**:
  - 443/tcp - HTTPS (for threat intel API calls)
  - 80/tcp - HTTP (for package updates)

### Access Requirements

- **SSH Access**: Key-based authentication only
- **Sudo Access**: Required for installation
- **Cloud Access** (if applicable): AWS/Azure/GCP credentials
- **Git Access**: Access to HP_TI repository
- **Secrets Access**: Access to secrets management system (Vault, AWS Secrets Manager)

### Pre-Deployment Checklist

- [ ] Hardware/VMs provisioned
- [ ] Operating system installed and updated
- [ ] Network connectivity verified
- [ ] DNS records configured
- [ ] SSL/TLS certificates obtained
- [ ] Firewall rules configured
- [ ] SSH key-based authentication configured
- [ ] Backup storage configured
- [ ] Monitoring infrastructure ready
- [ ] Team access configured
- [ ] Change request approved (if required)
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified

## Infrastructure Setup

### 1. Server Provisioning

#### Cloud Deployment (AWS Example)

```bash
# Launch EC2 instances
aws ec2 run-instances \
  --image-id ami-ubuntu-22.04 \
  --instance-type t3.xlarge \
  --key-name hp-ti-prod-key \
  --security-group-ids sg-hp-ti-prod \
  --subnet-id subnet-private-1a \
  --block-device-mappings '[
    {
      "DeviceName": "/dev/sda1",
      "Ebs": {
        "VolumeSize": 200,
        "VolumeType": "gp3",
        "Iops": 3000,
        "DeleteOnTermination": false
      }
    }
  ]' \
  --tag-specifications 'ResourceType=instance,Tags=[
    {Key=Name,Value=hp-ti-prod-app-01},
    {Key=Environment,Value=production},
    {Key=Project,Value=HP_TI}
  ]'

# Create RDS instance for PostgreSQL
aws rds create-db-instance \
  --db-instance-identifier hp-ti-prod-db \
  --db-instance-class db.t3.large \
  --engine postgres \
  --engine-version 15.3 \
  --master-username hp_ti_admin \
  --master-user-password <strong-password> \
  --allocated-storage 500 \
  --storage-type gp3 \
  --storage-encrypted \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --vpc-security-group-ids sg-hp-ti-db \
  --db-subnet-group-name hp-ti-db-subnet-group \
  --multi-az \
  --publicly-accessible false
```

#### On-Premises Deployment

```bash
# Connect to server
ssh -i hp-ti-prod-key.pem admin@production-server

# Update system
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get autoremove -y

# Install required packages
sudo apt-get install -y \
  docker.io \
  docker-compose \
  git \
  curl \
  wget \
  ufw \
  fail2ban \
  htop \
  iotop \
  net-tools \
  postgresql-client

# Enable Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker installation
docker --version
docker-compose --version
```

### 2. Storage Configuration

```bash
# Create directory structure
sudo mkdir -p /opt/hp_ti
sudo mkdir -p /var/log/hp_ti
sudo mkdir -p /var/backups/hp_ti
sudo mkdir -p /data/postgresql
sudo mkdir -p /data/elasticsearch
sudo mkdir -p /data/redis

# Set ownership
sudo chown -R $USER:$USER /opt/hp_ti
sudo chown -R 999:999 /data/postgresql  # PostgreSQL UID
sudo chown -R 1000:1000 /data/elasticsearch  # Elasticsearch UID
sudo chown -R 999:999 /data/redis  # Redis UID

# Set permissions
sudo chmod 750 /opt/hp_ti
sudo chmod 755 /var/log/hp_ti
sudo chmod 700 /var/backups/hp_ti
sudo chmod 700 /data/postgresql
sudo chmod 755 /data/elasticsearch
sudo chmod 700 /data/redis

# Configure log rotation
sudo tee /etc/logrotate.d/hp_ti <<EOF
/var/log/hp_ti/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 $USER $USER
    sharedscripts
    postrotate
        docker-compose -f /opt/hp_ti/docker-compose.yml restart honeypot > /dev/null 2>&1
    endscript
}
EOF
```

### 3. Network Configuration

```bash
# Configure firewall (UFW)
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH from management network only
sudo ufw allow from 10.0.0.0/8 to any port 22 comment 'SSH from management network'

# Allow honeypot services (public)
sudo ufw allow 2222/tcp comment 'SSH Honeypot'
sudo ufw allow 8080/tcp comment 'HTTP Honeypot'
sudo ufw allow 8443/tcp comment 'HTTPS Honeypot'
sudo ufw allow 2323/tcp comment 'Telnet Honeypot'
sudo ufw allow 2121/tcp comment 'FTP Honeypot'

# Enable firewall
sudo ufw --force enable
sudo ufw status verbose

# Configure sysctl for network optimization
sudo tee /etc/sysctl.d/99-hp_ti.conf <<EOF
# Network optimization
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_tw_reuse = 1

# Security hardening
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
EOF

sudo sysctl -p /etc/sysctl.d/99-hp_ti.conf
```

## Security Hardening

### 1. Run Security Hardening Script

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/org/HP_TI.git hp_ti
cd hp_ti

# Checkout production version
sudo git checkout tags/v1.2.3

# Run security hardening script
sudo ./deployment/security/hardening_script.sh --production

# This script will:
# - Update system packages
# - Configure firewall
# - Harden SSH
# - Install and configure fail2ban
# - Configure SELinux/AppArmor
# - Set file permissions
# - Harden Docker
# - Harden kernel parameters
# - Configure audit logging
# - Disable unnecessary services
# - Run security scans
```

### 2. SSL/TLS Certificate Configuration

```bash
# Option 1: Let's Encrypt (Free, automated)
sudo apt-get install -y certbot

# Obtain certificate
sudo certbot certonly --standalone \
  -d honeypot.example.com \
  --email admin@example.com \
  --agree-tos \
  --non-interactive

# Certificates will be in /etc/letsencrypt/live/honeypot.example.com/

# Set up auto-renewal
sudo crontab -e
# Add: 0 3 * * * certbot renew --quiet --post-hook "docker-compose -f /opt/hp_ti/docker-compose.yml restart"

# Option 2: Commercial Certificate
# Upload certificate files
sudo mkdir -p /opt/hp_ti/ssl
sudo cp cert.pem /opt/hp_ti/ssl/
sudo cp key.pem /opt/hp_ti/ssl/
sudo cp chain.pem /opt/hp_ti/ssl/

# Set permissions
sudo chmod 644 /opt/hp_ti/ssl/cert.pem
sudo chmod 600 /opt/hp_ti/ssl/key.pem
sudo chmod 644 /opt/hp_ti/ssl/chain.pem
```

### 3. Secrets Management

```bash
# Create secrets file (NEVER commit this to git)
cd /opt/hp_ti

# Option 1: Local .env file
cat > .env <<EOF
# Database
DB_HOST=hp-ti-db.internal
DB_PORT=5432
DB_NAME=hp_ti_db
DB_USER=hp_ti_user
DB_PASSWORD=$(openssl rand -base64 32)

# Redis
REDIS_HOST=hp-ti-redis.internal
REDIS_PORT=6379
REDIS_PASSWORD=$(openssl rand -base64 32)

# Elasticsearch
ES_HOST=hp-ti-es.internal
ES_PORT=9200
ES_USER=elastic
ES_PASSWORD=$(openssl rand -base64 32)

# Threat Intel API Keys
ABUSEIPDB_API_KEY=your_api_key_here
VIRUSTOTAL_API_KEY=your_api_key_here
SHODAN_API_KEY=your_api_key_here

# JWT Secret
JWT_SECRET=$(openssl rand -base64 64)

# Encryption Key
ENCRYPTION_KEY=$(openssl rand -base64 32)

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Email (for alerts)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=hp_ti@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_FROM=hp_ti@example.com
ALERT_EMAIL=security@example.com

# Slack (for alerts)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
EOF

# Secure the .env file
chmod 600 .env

# Option 2: HashiCorp Vault (Recommended for production)
# Install Vault client
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install vault

# Configure Vault
export VAULT_ADDR='https://vault.example.com:8200'
export VAULT_TOKEN='your-vault-token'

# Store secrets in Vault
vault kv put secret/hp_ti/production \
  db_password=$(openssl rand -base64 32) \
  redis_password=$(openssl rand -base64 32) \
  es_password=$(openssl rand -base64 32) \
  jwt_secret=$(openssl rand -base64 64) \
  encryption_key=$(openssl rand -base64 32) \
  abuseipdb_api_key="your_api_key" \
  virustotal_api_key="your_api_key"

# Create script to fetch secrets from Vault
cat > /opt/hp_ti/scripts/load_secrets.sh <<'EOF'
#!/bin/bash
SECRETS=$(vault kv get -format=json secret/hp_ti/production | jq -r '.data.data')
export DB_PASSWORD=$(echo $SECRETS | jq -r '.db_password')
export REDIS_PASSWORD=$(echo $SECRETS | jq -r '.redis_password')
# ... etc
EOF

chmod +x /opt/hp_ti/scripts/load_secrets.sh
```

## Application Deployment

### 1. Clone and Configure

```bash
# Already cloned in /opt/hp_ti

# Checkout production version
cd /opt/hp_ti
git checkout tags/v1.2.3

# Verify .env file
cat .env
# Ensure all required variables are set

# Update configuration files
cp config/production.yaml.example config/production.yaml
vim config/production.yaml
# Update with production-specific values
```

### 2. Initialize Database

```bash
# Create database and user (if using standalone PostgreSQL)
docker-compose up -d postgres

# Wait for PostgreSQL to be ready
sleep 30

# Create database
docker exec hp_ti_postgres psql -U postgres -c "CREATE DATABASE hp_ti_db;"
docker exec hp_ti_postgres psql -U postgres -c "CREATE USER hp_ti_user WITH ENCRYPTED PASSWORD 'your_password';"
docker exec hp_ti_postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE hp_ti_db TO hp_ti_user;"

# Run database initialization script
docker-compose run --rm honeypot python scripts/init_database.py

# Verify tables created
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "\dt"
```

### 3. Deploy Services

```bash
# Pull Docker images
docker-compose pull

# Start infrastructure services first
docker-compose up -d postgres redis elasticsearch

# Wait for services to be ready (2-3 minutes)
echo "Waiting for infrastructure services to start..."
sleep 120

# Verify infrastructure services
docker-compose ps
docker exec hp_ti_postgres pg_isready -U hp_ti_user
docker exec hp_ti_redis redis-cli ping
curl -s http://localhost:9200/_cluster/health | jq .

# Start application services
docker-compose up -d honeypot pipeline

# Verify all services running
docker-compose ps
```

### 4. Configure Elasticsearch Indices

```bash
# Create index templates
curl -X PUT "localhost:9200/_index_template/hp_ti_logs_template" \
  -H 'Content-Type: application/json' \
  -d @config/elasticsearch/index_template.json

# Create initial indices
curl -X PUT "localhost:9200/hp_ti_logs-$(date +%Y.%m.%d)" \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1
    }
  }'

# Configure index lifecycle management
curl -X PUT "localhost:9200/_ilm/policy/hp_ti_logs_policy" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "min_age": "0ms",
          "actions": {
            "rollover": {
              "max_size": "50GB",
              "max_age": "7d"
            }
          }
        },
        "warm": {
          "min_age": "7d",
          "actions": {
            "shrink": {
              "number_of_shards": 1
            }
          }
        },
        "delete": {
          "min_age": "90d",
          "actions": {
            "delete": {}
          }
        }
      }
    }
  }'

# Configure snapshot repository for backups
curl -X PUT "localhost:9200/_snapshot/hp_ti_backups" \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "fs",
    "settings": {
      "location": "/usr/share/elasticsearch/backups"
    }
  }'
```

## Post-Deployment Verification

### 1. Run Health Checks

```bash
# Run comprehensive health check
./deployment/scripts/health_check.sh --post-deploy

# Expected output:
# ✓ Docker daemon
# ✓ Honeypot container
# ✓ PostgreSQL container
# ✓ Elasticsearch container
# ✓ Redis container
# ✓ Honeypot SSH service
# ✓ Honeypot HTTP service
# ✓ Metrics endpoint
# ✓ PostgreSQL connection
# ✓ Elasticsearch health
# ✓ Redis ping
# ✓ Disk space (> 20% free)
# ✓ Memory available
# All health checks passed!
```

### 2. Functional Testing

```bash
# Test SSH honeypot
nc -zv localhost 2222
# Or from external machine:
nc -zv honeypot.example.com 2222

# Test HTTP honeypot
curl -I http://localhost:8080
curl -I https://honeypot.example.com

# Test Telnet honeypot
telnet localhost 2323

# Verify logs are being captured
sleep 60
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM honeypot_events WHERE created_at > NOW() - INTERVAL '5 minutes';"

# Should return > 0 if connections being logged

# Verify Elasticsearch ingestion
curl -s "localhost:9200/hp_ti_logs-*/_count" | jq .
```

### 3. Performance Testing

```bash
# Test connection handling capacity
# Use a load testing tool like hey or ab

# Install hey
go install github.com/rakyll/hey@latest

# Test HTTP honeypot (1000 requests, 50 concurrent)
hey -n 1000 -c 50 -m GET http://localhost:8080/

# Review metrics
# - Requests per second should be > 100
# - p95 latency should be < 500ms
# - Error rate should be 0%

# Test database performance
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "
EXPLAIN ANALYZE
SELECT * FROM honeypot_events
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 100;"

# Query should complete in < 100ms
```

### 4. Security Verification

```bash
# Verify firewall rules
sudo ufw status verbose

# Verify SSH hardening
sudo sshd -T | grep -E "permitrootlogin|passwordauthentication|pubkeyauthentication"
# Should show:
# permitrootlogin no
# passwordauthentication no
# pubkeyauthentication yes

# Verify fail2ban
sudo fail2ban-client status sshd

# Verify Docker security
docker run --rm -it alpine sh
# Inside container:
whoami  # Should NOT be root
cat /proc/1/status | grep CapEff
# Should show limited capabilities

# Run security audit
sudo lynis audit system --quick

# Review results and address any warnings
```

## Monitoring Setup

### 1. Configure Prometheus

```bash
# Prometheus is included in docker-compose.yml
# Verify Prometheus is running
curl -s http://localhost:9090/-/healthy

# Import recording rules and alerts
docker exec hp_ti_prometheus \
  promtool check config /etc/prometheus/prometheus.yml

# Verify targets are being scraped
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

### 2. Configure Grafana

```bash
# Access Grafana
# http://localhost:3000
# Default credentials: admin/admin (change immediately)

# Import dashboards from visualization/dashboards/
# - overview.json
# - attack_analysis.json
# - pipeline_health.json

# Configure data source:
# - Type: Prometheus
# - URL: http://prometheus:9090

# Set up alerting
# Configure alert notification channels (Email, Slack, PagerDuty)
```

### 3. Configure Alert Manager

```bash
# Alert Manager configuration already in config/alerts_config.yaml

# Verify alert rules loaded
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {alert: .name, state: .state}'

# Test alert delivery
# Trigger a test alert
docker-compose stop honeypot
# Wait 2 minutes
# Should receive alert

# Restart service
docker-compose up -d honeypot
```

### 4. Log Aggregation

```bash
# Verify logs flowing to Elasticsearch
curl -s "localhost:9200/hp_ti_logs-*/_search?size=10" | jq '.hits.hits[]._source' | head -20

# Access Kibana (if deployed)
# http://localhost:5601

# Create index pattern: hp_ti_logs-*
# Explore logs in Discover tab
```

## Backup Configuration

### 1. Configure Automated Backups

```bash
# Create backup directory on remote storage
# For S3:
aws s3 mb s3://hp-ti-production-backups

# Configure S3 credentials
aws configure

# Set up automated daily backups
sudo crontab -e

# Add cron job for daily backup at 2 AM
0 2 * * * /opt/hp_ti/deployment/scripts/backup.sh > /var/log/hp_ti/backup.log 2>&1

# Test backup
./deployment/scripts/backup.sh

# Verify backup created
ls -lh /var/backups/hp_ti/
aws s3 ls s3://hp-ti-production-backups/
```

### 2. Test Restore Procedure

```bash
# Test restore on a separate test environment
# DO NOT RUN ON PRODUCTION

# On test server:
./deployment/scripts/restore.sh --backup 20250115_143000

# Verify restore successful
./deployment/scripts/health_check.sh

# Document restore time for RTO planning
```

## Operational Handoff

### 1. Documentation Handoff

Ensure the operations team has access to:

- [ ] This deployment guide
- [ ] All operational playbooks (incident response, rollback, disaster recovery, scaling)
- [ ] Architecture diagrams
- [ ] Configuration documentation
- [ ] Secrets location and access procedures
- [ ] Contact list for escalations
- [ ] Vendor support contracts

### 2. Access Provisioning

- [ ] SSH access for operations team
- [ ] Grafana access
- [ ] Kibana access (if applicable)
- [ ] Database read-only access
- [ ] Cloud console access (AWS/Azure/GCP)
- [ ] Secrets management access
- [ ] Git repository access

### 3. Training

- [ ] Walkthrough of system architecture
- [ ] Demonstration of monitoring dashboards
- [ ] Review of common operational tasks
- [ ] Practice incident response scenarios
- [ ] Review of backup and restore procedures
- [ ] Review of deployment procedures

### 4. Runbook Review

Review these playbooks with the operations team:

- [ ] `docs/playbooks/incident_response.md`
- [ ] `docs/playbooks/deployment.md`
- [ ] `docs/playbooks/rollback.md`
- [ ] `docs/playbooks/disaster_recovery.md`
- [ ] `docs/playbooks/scaling.md`

### 5. Monitoring Handoff

- [ ] Review Grafana dashboards
- [ ] Review alert rules and thresholds
- [ ] Configure alert notification channels
- [ ] Set up on-call rotation
- [ ] Test alert delivery
- [ ] Document escalation procedures

### 6. Support Transition

- [ ] Define SLAs for incident response
- [ ] Establish communication channels (Slack, PagerDuty, email)
- [ ] Schedule regular check-ins (daily for first week, weekly for first month)
- [ ] Document known issues and workarounds
- [ ] Provide development team contact information for escalations

## Post-Deployment Monitoring

### First 24 Hours

- [ ] Monitor dashboards continuously
- [ ] Review logs every hour
- [ ] Check alert status every hour
- [ ] Verify backup completed successfully
- [ ] Monitor resource utilization
- [ ] Check for any anomalies

### First Week

- [ ] Daily health checks
- [ ] Daily review of error logs
- [ ] Daily review of performance metrics
- [ ] Weekly performance report
- [ ] Tune alert thresholds if needed

### First Month

- [ ] Weekly performance reviews
- [ ] Weekly capacity planning review
- [ ] Monthly incident review
- [ ] Review and optimize configurations
- [ ] Plan for any needed improvements

## Troubleshooting

See `docs/deployment/troubleshooting.md` for common issues and solutions.

## Rollback Plan

If critical issues are discovered post-deployment:

1. Follow procedures in `docs/playbooks/rollback.md`
2. Notify all stakeholders immediately
3. Execute rollback within 30 minutes
4. Conduct post-incident review within 24 hours

## Success Criteria

Deployment is considered successful when:

- [ ] All health checks passing
- [ ] All services running and stable
- [ ] Honeypot services accepting connections
- [ ] Logs being captured and stored
- [ ] Metrics being collected
- [ ] Alerts configured and tested
- [ ] Backups configured and tested
- [ ] No critical errors in logs for 24 hours
- [ ] Performance meeting SLA requirements
- [ ] Security hardening complete
- [ ] Operations team trained and onboarded
- [ ] Documentation complete and accessible

## Support and Escalation

For deployment support:

1. **Level 1**: Operations Team - [Email] - [Slack Channel]
2. **Level 2**: Technical Lead - [Name] - [Phone] - [Email]
3. **Level 3**: Engineering Manager - [Name] - [Phone] - [Email]
4. **Level 4**: CTO - [Name] - [Phone] - [Email]

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
**Owner**: DevOps Team
