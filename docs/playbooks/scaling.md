# HP_TI Scaling Playbook

## Overview

This playbook provides procedures for scaling the HP_TI platform to handle increased load, whether due to organic growth or attack campaigns.

## Scaling Triggers

### When to Scale

Monitor these metrics and scale when thresholds are exceeded:

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|------------------|-------------------|--------|
| **CPU Usage** | 70% sustained | 85% sustained | Scale horizontally |
| **Memory Usage** | 75% | 90% | Scale vertically or horizontally |
| **Disk I/O Wait** | 20% | 40% | Add faster disks or scale out |
| **Database Connections** | 70% of max | 90% of max | Increase connection pool or add read replicas |
| **API Response Time** | p95 > 500ms | p95 > 1000ms | Scale application tier |
| **Queue Depth** | > 10,000 items | > 50,000 items | Scale workers |
| **Elasticsearch JVM Heap** | 75% | 85% | Increase heap or add nodes |
| **Incoming Connection Rate** | > 1000/sec | > 5000/sec | Scale honeypot services |

### Monitoring for Scaling Signals

```bash
# Check current resource utilization
docker stats --no-stream

# Check database connection count
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check pipeline queue depth
curl -s http://localhost:9091/metrics | grep pipeline_queue_size

# Check request latency
curl -s http://localhost:9090/metrics | grep honeypot_request_duration_seconds | grep quantile

# Check Elasticsearch cluster stats
curl -s "localhost:9200/_cluster/stats?pretty"
```

## Scaling Strategies

### 1. Vertical Scaling (Scale Up)

**When to Use**:
- Simple, single-instance deployments
- Database bottlenecks
- Quick temporary relief
- < 100% capacity increase needed

**Limitations**:
- Downtime required
- Maximum instance size limits
- Single point of failure remains
- Cost inefficient at large scale

#### Procedure: Scale Up Database

```bash
# 1. Announce maintenance window
# Expected downtime: 15-30 minutes

# 2. Create backup
./deployment/scripts/backup.sh --database-only

# 3. Stop application
docker-compose stop honeypot pipeline

# 4. Export database
docker exec hp_ti_postgres pg_dumpall -U hp_ti_user | gzip > /tmp/db_migration.sql.gz

# 5. Update docker-compose.yml with more resources
# Edit docker-compose.yml:
services:
  postgres:
    ...
    deploy:
      resources:
        limits:
          cpus: '4'      # Increase from 2
          memory: 8G     # Increase from 4G
        reservations:
          cpus: '2'
          memory: 4G

# 6. Recreate container with new limits
docker-compose up -d postgres

# 7. Verify new resources
docker stats hp_ti_postgres --no-stream

# 8. Start application
docker-compose up -d

# 9. Verify health
./deployment/scripts/health_check.sh

# 10. Monitor for 1 hour
watch -n 60 'docker stats --no-stream'
```

#### Procedure: Scale Up Elasticsearch

```bash
# 1. Increase JVM heap size
# Edit docker-compose.yml:
services:
  elasticsearch:
    environment:
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"  # Increase from 2g
    deploy:
      resources:
        limits:
          memory: 8G  # Increase from 4G

# 2. Restart Elasticsearch
docker-compose up -d elasticsearch

# 3. Wait for cluster to stabilize (2-5 minutes)
watch -n 10 'curl -s "localhost:9200/_cluster/health?pretty"'

# 4. Verify heap increase
curl -s "localhost:9200/_nodes/stats/jvm?pretty" | grep heap_max_in_bytes
```

### 2. Horizontal Scaling (Scale Out)

**When to Use**:
- High availability required
- Load distribution needed
- > 100% capacity increase
- Long-term growth

**Benefits**:
- No downtime
- Better fault tolerance
- Flexible capacity
- Cost efficient at scale

#### Architecture: Horizontally Scaled HP_TI

```
                    Load Balancer (nginx/HAProxy)
                            |
        +-------------------+-------------------+
        |                   |                   |
   HP_TI Node 1        HP_TI Node 2        HP_TI Node 3
   (Honeypot +         (Honeypot +         (Honeypot +
    Pipeline)           Pipeline)           Pipeline)
        |                   |                   |
        +-------------------+-------------------+
                            |
                    Shared Data Layer
                            |
        +-------------------+-------------------+
        |                   |                   |
   PostgreSQL          Elasticsearch        Redis
   (Primary +          (Cluster:            (Primary +
    Replicas)          3+ nodes)            Replicas)
```

#### Procedure: Add Application Node

```bash
# 1. Provision new server
# Cloud: Launch new instance from base image
# On-prem: Deploy to spare server

# 2. On new server, install HP_TI
ssh new-node
cd /opt
git clone https://github.com/org/HP_TI.git hp_ti
cd hp_ti
git checkout tags/v1.2.3

# 3. Configure to use shared database
cp /opt/hp_ti/.env.example /opt/hp_ti/.env
# Edit .env:
# DB_HOST=primary-db-server  # Point to primary DB
# REDIS_HOST=primary-redis-server
# ES_HOST=primary-es-server

# 4. Start only application services (not databases)
docker-compose up -d honeypot pipeline

# 5. Verify health
./deployment/scripts/health_check.sh

# 6. Add to load balancer
# On load balancer server:
sudo vim /etc/nginx/conf.d/hp_ti.conf

# Add to upstream block:
upstream hp_ti_honeypot {
    least_conn;
    server node1:2222;
    server node2:2222;
    server new-node:2222;  # Add new node
}

upstream hp_ti_http {
    least_conn;
    server node1:8080;
    server node2:8080;
    server new-node:8080;  # Add new node
}

# 7. Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx

# 8. Monitor new node
watch -n 30 'ssh new-node "docker stats --no-stream"'
```

#### Procedure: Scale PostgreSQL with Read Replicas

```bash
# Use case: Read-heavy workload, many analytical queries

# 1. Set up streaming replication on primary
# On primary DB server:
docker exec hp_ti_postgres psql -U hp_ti_user -c \
  "CREATE USER replicator REPLICATION LOGIN ENCRYPTED PASSWORD 'replica_password';"

# Edit postgresql.conf:
# wal_level = replica
# max_wal_senders = 3
# wal_keep_size = 1GB

# Edit pg_hba.conf:
# host replication replicator replica_ip/32 md5

# Restart PostgreSQL
docker-compose restart postgres

# 2. Set up replica server
# On replica server:
docker run -d \
  --name hp_ti_postgres_replica \
  -e POSTGRES_PASSWORD=replica_password \
  -v /var/lib/postgresql/data:/var/lib/postgresql/data \
  postgres:15

# 3. Create base backup from primary
docker exec hp_ti_postgres_replica \
  pg_basebackup -h primary_ip -D /var/lib/postgresql/data -U replicator -P -v -R -X stream -C -S replica1

# 4. Replica will start streaming from primary automatically

# 5. Verify replication
# On primary:
docker exec hp_ti_postgres psql -U hp_ti_user -c \
  "SELECT client_addr, state, sync_state FROM pg_stat_replication;"

# On replica:
docker exec hp_ti_postgres_replica psql -U hp_ti_user -c \
  "SELECT pg_is_in_recovery(), pg_last_wal_receive_lsn();"

# 6. Update application to use read replica for queries
# In application code or connection pool:
# WRITE_DB_HOST=primary_ip
# READ_DB_HOST=replica_ip

# Configure pgBouncer for automatic read/write splitting (advanced)
```

#### Procedure: Scale Elasticsearch Cluster

```bash
# 1. Add new Elasticsearch node
# On new server:
docker run -d \
  --name hp_ti_elasticsearch \
  --network hp_ti_network \
  -e "cluster.name=hp_ti_cluster" \
  -e "node.name=es-node-3" \
  -e "discovery.seed_hosts=es-node-1,es-node-2" \
  -e "cluster.initial_master_nodes=es-node-1,es-node-2,es-node-3" \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  -p 9200:9200 \
  -p 9300:9300 \
  elasticsearch:8.5.0

# 2. Verify node joined cluster
curl -s "localhost:9200/_cat/nodes?v"

# 3. Check cluster health (should turn green)
curl -s "localhost:9200/_cluster/health?pretty"

# 4. Rebalance shards
curl -X POST "localhost:9200/_cluster/reroute?retry_failed=true"

# 5. Monitor rebalancing
watch -n 10 'curl -s "localhost:9200/_cat/shards?v&h=index,shard,prirep,state,node"'

# 6. Update application configuration to use all nodes
# Edit .env:
ES_HOSTS=es-node-1:9200,es-node-2:9200,es-node-3:9200
```

### 3. Auto-Scaling (Cloud Environments)

**Prerequisites**:
- Cloud-native deployment (AWS, Azure, GCP)
- Containerized application
- Stateless application tier
- Shared/external data layer

#### AWS Auto Scaling Group Setup

```bash
# 1. Create Launch Template
aws ec2 create-launch-template \
  --launch-template-name hp-ti-app-template \
  --version-description "HP_TI Application v1.2.3" \
  --launch-template-data file://launch-template.json

# launch-template.json:
{
  "ImageId": "ami-hp-ti-base",
  "InstanceType": "t3.large",
  "KeyName": "hp-ti-key",
  "SecurityGroupIds": ["sg-hp-ti"],
  "UserData": "<base64-encoded-startup-script>",
  "IamInstanceProfile": {
    "Name": "hp-ti-instance-profile"
  },
  "TagSpecifications": [{
    "ResourceType": "instance",
    "Tags": [{"Key": "Name", "Value": "hp-ti-app"}]
  }]
}

# 2. Create Auto Scaling Group
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name hp-ti-asg \
  --launch-template LaunchTemplateName=hp-ti-app-template,Version='$Latest' \
  --min-size 2 \
  --max-size 10 \
  --desired-capacity 3 \
  --target-group-arns arn:aws:elasticloadbalancing:region:account:targetgroup/hp-ti-tg/xxx \
  --health-check-type ELB \
  --health-check-grace-period 300 \
  --vpc-zone-identifier "subnet-1,subnet-2,subnet-3"

# 3. Create Scaling Policies

# Scale up policy
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name hp-ti-asg \
  --policy-name scale-up \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration file://scale-up-policy.json

# scale-up-policy.json:
{
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ASGAverageCPUUtilization"
  },
  "TargetValue": 70.0
}

# 4. Create CloudWatch Alarms for custom metrics
aws cloudwatch put-metric-alarm \
  --alarm-name hp-ti-high-connections \
  --alarm-description "Scale up when connection rate high" \
  --metric-name ConnectionsPerSecond \
  --namespace HP_TI \
  --statistic Average \
  --period 300 \
  --threshold 1000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:autoscaling:region:account:scalingPolicy:xxx
```

#### Kubernetes Horizontal Pod Autoscaler

```yaml
# hp-ti-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hp-ti-honeypot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hp-ti-honeypot
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 75
  - type: Pods
    pods:
      metric:
        name: honeypot_connections_per_second
      target:
        type: AverageValue
        averageValue: "100"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 4
        periodSeconds: 30
      selectPolicy: Max
```

```bash
# Apply HPA
kubectl apply -f hp-ti-hpa.yaml

# Monitor autoscaling
kubectl get hpa hp-ti-honeypot-hpa --watch

# View scaling events
kubectl describe hpa hp-ti-honeypot-hpa
```

### 4. Database Sharding (Advanced)

**When to Use**:
- > 1TB database size
- > 100,000 writes/sec
- Geographic distribution needed
- Read replicas insufficient

#### Sharding Strategy for HP_TI

```sql
-- Shard by time (recommended for honeypot logs)
-- Shard 1: Events from 2025-01-01 to 2025-01-31
-- Shard 2: Events from 2025-02-01 to 2025-02-28
-- Shard 3: Events from 2025-03-01 to 2025-03-31

-- Or shard by source IP hash
-- Shard 1: hash(source_ip) % 4 == 0
-- Shard 2: hash(source_ip) % 4 == 1
-- Shard 3: hash(source_ip) % 4 == 2
-- Shard 4: hash(source_ip) % 4 == 3

-- Use PostgreSQL native partitioning
CREATE TABLE honeypot_events (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    source_ip INET NOT NULL,
    -- ... other columns
) PARTITION BY RANGE (timestamp);

-- Create partitions (monthly)
CREATE TABLE honeypot_events_2025_01 PARTITION OF honeypot_events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE honeypot_events_2025_02 PARTITION OF honeypot_events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Automatic partition creation (using pg_partman extension)
SELECT create_parent('public.honeypot_events', 'timestamp', 'native', 'monthly');
SELECT update_partition_auto_append('public.honeypot_events');
```

## Load Balancing

### nginx Configuration

```nginx
# /etc/nginx/conf.d/hp_ti.conf

upstream hp_ti_ssh_honeypot {
    least_conn;  # Route to server with fewest connections

    server node1:2222 max_fails=3 fail_timeout=30s;
    server node2:2222 max_fails=3 fail_timeout=30s;
    server node3:2222 max_fails=3 fail_timeout=30s;

    # Backup server
    server node4:2222 backup;
}

upstream hp_ti_http_honeypot {
    ip_hash;  # Sticky sessions based on source IP

    server node1:8080 weight=3;
    server node2:8080 weight=3;
    server node3:8080 weight=2;  # Lower weight for smaller instance
}

# SSH honeypot (TCP stream)
stream {
    server {
        listen 2222;
        proxy_pass hp_ti_ssh_honeypot;
        proxy_connect_timeout 1s;
    }
}

# HTTP honeypot
server {
    listen 80;
    listen 443 ssl;
    server_name honeypot.example.com;

    location / {
        proxy_pass http://hp_ti_http_honeypot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Health check
        proxy_next_upstream error timeout http_500 http_502 http_503;
    }
}

# Health check endpoint
server {
    listen 8081;
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### HAProxy Configuration

```haproxy
# /etc/haproxy/haproxy.cfg

global
    maxconn 50000
    log /dev/log local0
    user haproxy
    group haproxy
    daemon

defaults
    mode http
    log global
    option httplog
    option dontlognull
    timeout connect 5000
    timeout client  50000
    timeout server  50000

# Stats page
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats auth admin:password

# SSH Honeypot (TCP mode)
frontend ssh_honeypot_front
    mode tcp
    bind *:2222
    default_backend ssh_honeypot_back

backend ssh_honeypot_back
    mode tcp
    balance leastconn
    option tcp-check
    server node1 10.0.1.10:2222 check
    server node2 10.0.1.11:2222 check
    server node3 10.0.1.12:2222 check

# HTTP Honeypot
frontend http_honeypot_front
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/honeypot.pem
    default_backend http_honeypot_back

backend http_honeypot_back
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    server node1 10.0.1.10:8080 check
    server node2 10.0.1.11:8080 check
    server node3 10.0.1.12:8080 check
```

## Scaling Checklist

### Before Scaling

- [ ] Identify bottleneck (CPU, memory, disk, network, database)
- [ ] Review current utilization metrics
- [ ] Estimate required capacity increase
- [ ] Determine scaling strategy (vertical vs horizontal)
- [ ] Create backup before making changes
- [ ] Notify team of scaling activities
- [ ] Plan for rollback if needed

### During Scaling

- [ ] Execute scaling procedure
- [ ] Monitor system during scaling
- [ ] Verify new resources allocated
- [ ] Update load balancer configuration
- [ ] Test connectivity to new resources
- [ ] Check for errors in logs

### After Scaling

- [ ] Verify health checks passing
- [ ] Monitor performance metrics (1 hour minimum)
- [ ] Verify load distribution across instances
- [ ] Check for any anomalies or errors
- [ ] Update documentation with new capacity
- [ ] Document scaling action and results
- [ ] Review and optimize if needed

## Cost Optimization

### Right-Sizing

```bash
# Review actual resource usage over 30 days
# If consistently under-utilized, scale down

# Check average CPU usage
docker stats --no-stream | awk '{print $1,$3}' | column -t

# Check average memory usage
free -h

# Database connection usage
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# If usage < 50% consistently, consider scaling down
```

### Scheduled Scaling

```bash
# Scale up during known high-traffic periods
# Scale down during low-traffic periods (e.g., nights, weekends)

# Example: AWS scheduled scaling
aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name hp-ti-asg \
  --scheduled-action-name scale-up-morning \
  --recurrence "0 8 * * 1-5" \
  --desired-capacity 5

aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name hp-ti-asg \
  --scheduled-action-name scale-down-evening \
  --recurrence "0 20 * * 1-5" \
  --desired-capacity 2
```

## Monitoring Post-Scaling

```bash
# Key metrics to monitor after scaling:

# 1. Resource utilization (should decrease)
docker stats --no-stream

# 2. Response times (should improve)
curl -s http://localhost:9090/metrics | grep request_duration_seconds

# 3. Error rates (should remain stable or decrease)
docker-compose logs --tail=500 | grep -i "error" | wc -l

# 4. Database connections (should distribute across replicas)
docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# 5. Queue depths (should decrease)
curl -s http://localhost:9091/metrics | grep pipeline_queue_size

# 6. Cost (monitor cloud billing)
aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity DAILY --metrics BlendedCost
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Next Review**: 2025-04-15
**Owner**: Infrastructure Team
