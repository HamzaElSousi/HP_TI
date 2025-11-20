# HP_TI System Architecture

## Overview

The HP_TI (Honeypot & Threat Intelligence) system is designed as a modular, scalable platform for detecting, capturing, and analyzing malicious network activity. This document describes the high-level architecture, component interactions, and design decisions.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Internet / Attackers                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ Malicious Traffic
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Honeypot Services Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │   SSH    │  │   HTTP   │  │  Telnet  │  │   FTP    │            │
│  │ Honeypot │  │ Honeypot │  │ Honeypot │  │ Honeypot │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │             │              │             │                   │
│       └─────────────┴──────────────┴─────────────┘                  │
│                             │                                        │
│                             │ Structured Logs                        │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Data Ingestion Pipeline                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │  Log Collector │→ │  Log Parser    │→ │  Validator     │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│                             │                                        │
│                             │ Parsed Events                          │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ Enrichment  │  │  Storage    │  │   Alert     │
    │   Engine    │  │   Layer     │  │   Engine    │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                │                │
           │                │                │
           ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  External   │  │ PostgreSQL  │  │   Slack/    │
    │   Threat    │  │   + Elastic │  │   Email     │
    │    Intel    │  │   Search    │  │             │
    └─────────────┘  └──────┬──────┘  └─────────────┘
                            │
                            │ Enriched Data
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Visualization & Analysis                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │    Grafana     │  │     Kibana     │  │    Reports     │        │
│  │   Dashboards   │  │  Log Explorer  │  │   Generator    │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    Security Analysts
```

## Component Architecture

### 1. Honeypot Services Layer

**Purpose**: Simulate vulnerable services to attract and capture attacker activity

**Components**:
- **SSH Honeypot**: Emulates SSH service, captures credentials and commands
- **HTTP Honeypot**: Fake web applications, detects web-based attacks
- **Telnet Honeypot**: Simulates IoT devices and legacy systems
- **FTP Honeypot**: Fake file server, captures file operations

**Design Principles**:
- Low-interaction honeypots (no real shells or services)
- Containerized for isolation
- Fail-safe design (attacks cannot pivot)
- Realistic responses to avoid detection
- Comprehensive logging of all interactions

**Technology Stack**:
- Python 3.9+ with asyncio
- Paramiko for SSH protocol
- Flask for HTTP service
- Custom protocol handlers for Telnet/FTP
- Docker for containerization

### 2. Data Ingestion Pipeline

**Purpose**: Collect, parse, and normalize logs from all honeypot services

**Components**:

**Log Collector**:
- Monitors log files in real-time
- Supports multiple input formats
- Handles log rotation
- Buffers events for reliability

**Log Parser**:
- Service-specific parsers
- Data normalization
- Field extraction and validation
- Schema enforcement using Pydantic

**Validator**:
- Data quality checks
- Malformed event handling
- Dead letter queue for failed events
- Metrics on parsing success/failure

**Design Principles**:
- At-least-once delivery guarantee
- Schema validation at ingestion
- Clear separation between raw and processed data
- Backpressure handling
- Observability at each stage

**Technology Stack**:
- Python asyncio for async processing
- Pydantic for data validation
- File watchers (watchdog library)
- Optional: Kafka for high-scale scenarios

### 3. Enrichment Engine

**Purpose**: Augment captured data with external threat intelligence

**Components**:

**Enrichment Manager**:
- Orchestrates enrichment from multiple sources
- Handles API rate limiting
- Implements retry logic with exponential backoff
- Tracks enrichment coverage

**Enrichment Sources**:
1. **GeoIP** (MaxMind): Geographic location
2. **AbuseIPDB**: IP reputation and abuse scores
3. **WHOIS**: ASN, organization, ISP information
4. **VPN Detection**: Identifies proxies, VPNs, Tor
5. **VirusTotal**: IP reputation, passive DNS

**Cache Manager**:
- Redis-based distributed cache
- TTL per enrichment type
- Cache warming for known malicious IPs
- Metrics on cache hit/miss rates

**Design Principles**:
- Asynchronous enrichment (non-blocking)
- Graceful degradation if APIs unavailable
- Cost optimization through caching
- Multiple data sources for confidence scoring
- Privacy-aware (no PII collection)

**Technology Stack**:
- Python asyncio/httpx for async API calls
- Redis for caching
- Rate limiting (ratelimit library)
- Circuit breaker pattern for API failures

### 4. Storage Layer

**Purpose**: Persist raw logs, processed events, and enriched data

**Components**:

**Elasticsearch**:
- Primary storage for logs and events
- Full-text search capabilities
- Time-series data with ILM policies
- Index per day/week pattern

**PostgreSQL**:
- Structured threat intelligence data
- Relational queries (sessions, IPs, commands)
- ACID compliance for critical data
- Point-in-time recovery

**Redis**:
- Caching layer
- Session state (optional)
- Real-time counters and metrics

**S3/Object Storage**:
- Long-term log archival
- Cold storage (>90 days)
- Compliance and audit logs

**Design Principles**:
- Polyglot persistence (right tool for each job)
- Data lifecycle management
- Automated backups and retention
- Query optimization (indexes, partitioning)
- Separation of hot/warm/cold data

**Technology Stack**:
- Elasticsearch 8.x
- PostgreSQL 14+
- Redis 7+
- S3-compatible object storage

### 5. Alerting Engine

**Purpose**: Detect significant events and notify analysts

**Components**:

**Alert Rules Engine**:
- Configurable alert rules (YAML)
- Threshold-based alerts
- Pattern-based alerts
- Anomaly detection (future)

**Alert Manager**:
- Alert deduplication
- Alert aggregation
- Severity classification
- Escalation logic

**Notification Channels**:
- Email (critical alerts)
- Slack/Discord webhooks
- PagerDuty (production)
- Webhook for custom integrations

**Design Principles**:
- Low false positive rate
- Actionable alerts only
- Context-rich notifications
- Alert fatigue prevention
- Configurable severity levels

**Technology Stack**:
- Python with APScheduler for rule evaluation
- Jinja2 for alert templates
- SMTP, webhook clients

### 6. Visualization & Analysis

**Purpose**: Provide insights into captured threat data

**Components**:

**Grafana Dashboards**:
- Real-time metrics and trends
- Attack analytics
- Geographic visualizations
- Service health monitoring

**Kibana**:
- Log exploration and search
- Ad-hoc analysis
- Custom visualizations
- Saved queries for investigations

**Report Generator**:
- Automated daily/weekly reports
- Executive summaries
- PDF/HTML export
- Email delivery

**Design Principles**:
- Real-time or near-real-time updates
- Intuitive and actionable visualizations
- Drill-down capabilities
- Export and sharing capabilities
- Role-based access control (RBAC)

**Technology Stack**:
- Grafana 9+
- Kibana 8+
- Custom Python report generator
- Chart.js for custom visualizations

## Data Flow

### 1. Attack Capture Flow

```
1. Attacker connects to honeypot service
2. Honeypot logs connection metadata (IP, port, timestamp)
3. Attacker attempts authentication
4. Honeypot captures credentials, logs attempt
5. Honeypot provides fake access (if designed)
6. Attacker executes commands
7. Honeypot logs each command and response
8. Session ends, honeypot logs session summary
9. All events written to structured log files
```

### 2. Data Processing Flow

```
1. Log collector detects new log entries
2. Parser extracts fields from log lines
3. Validator checks schema compliance
4. Valid events sent to enrichment queue
5. Invalid events sent to dead letter queue
6. Enrichment engine processes events
   a. Check cache for existing enrichment
   b. Query external APIs if cache miss
   c. Aggregate enrichment data
   d. Update cache
7. Enriched event stored in Elasticsearch + PostgreSQL
8. Alert engine evaluates event against rules
9. If alert triggered, notification sent
10. Metrics updated (Prometheus)
```

### 3. Query & Analysis Flow

```
1. Analyst accesses Grafana dashboard
2. Grafana queries Prometheus for metrics
3. Grafana queries Elasticsearch for events
4. Dashboard renders visualizations
5. Analyst drills down into specific IP
6. Kibana provides detailed log search
7. Analyst identifies attack pattern
8. Analyst exports findings as report
```

## Security Architecture

### Network Segmentation

```
┌─────────────────────────────────────────────────────────┐
│                      DMZ / Public Zone                   │
│  ┌──────────────────────────────────────────┐           │
│  │      Honeypot Services (Containerized)   │           │
│  │  - No outbound access                    │           │
│  │  - Limited resources                     │           │
│  │  - Read-only filesystem                  │           │
│  └──────────────────────────────────────────┘           │
└────────────────────┬────────────────────────────────────┘
                     │ One-way logging
                     │ (honeypots → log aggregator)
                     ▼
┌─────────────────────────────────────────────────────────┐
│                      Processing Zone                     │
│  ┌──────────────────────────────────────────┐           │
│  │  Data Pipeline, Enrichment, Alerting     │           │
│  │  - Controlled outbound access (APIs)     │           │
│  │  - No inbound from DMZ except logs       │           │
│  └──────────────────────────────────────────┘           │
└────────────────────┬────────────────────────────────────┘
                     │ Processed data
                     ▼
┌─────────────────────────────────────────────────────────┐
│                      Data Zone (Private)                 │
│  ┌──────────────────────────────────────────┐           │
│  │  Databases, Storage                      │           │
│  │  - No direct external access             │           │
│  │  - Encrypted at rest and in transit      │           │
│  └──────────────────────────────────────────┘           │
└────────────────────┬────────────────────────────────────┘
                     │ Read queries
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Management Zone                       │
│  ┌──────────────────────────────────────────┐           │
│  │  Grafana, Kibana, Admin Tools            │           │
│  │  - HTTPS only                            │           │
│  │  - Authentication required               │           │
│  │  - VPN access only                       │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

### Security Controls

**Honeypot Isolation**:
- Containers with minimal privileges
- No outbound network access
- Resource limits (CPU, memory, disk)
- Read-only root filesystem
- AppArmor/SELinux profiles
- Regular security scanning

**Data Protection**:
- All data encrypted at rest (AES-256)
- TLS 1.3 for all internal communications
- Secrets in environment variables or vault
- No credentials in code or logs
- Regular backup encryption

**Access Control**:
- Role-based access control (RBAC)
- MFA for admin access
- VPN required for management interfaces
- Audit logging of all access
- Session timeout enforcement

**Monitoring**:
- Intrusion detection (OSSEC/Wazuh)
- File integrity monitoring
- Log aggregation and correlation
- Anomaly detection on honeypot behavior
- Regular security audits

## Scalability Architecture

### Horizontal Scaling

**Honeypot Services**:
- Stateless design enables easy replication
- Load balancer distributes traffic (optional)
- Each honeypot instance is independent
- Scale by adding more containers/VMs

**Data Pipeline**:
- Queue-based decoupling (Kafka/RabbitMQ)
- Multiple consumer instances
- Partition data by service or time
- Auto-scaling based on queue depth

**Storage**:
- Elasticsearch cluster (3+ nodes)
- PostgreSQL read replicas
- Redis cluster for high availability
- Sharding for very large datasets

**Processing**:
- Enrichment workers can be scaled independently
- Async processing with worker pools
- Batch processing for efficiency
- Backpressure handling

### Vertical Scaling

- Elasticsearch: Increase heap size, add RAM
- PostgreSQL: Larger instance, more CPU/RAM
- Redis: More memory for larger cache
- Application: More CPU for parsing/enrichment

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Honeypot response time | <100ms | Average connection accept time |
| Log ingestion latency | <10s | Event capture to storage |
| Enrichment latency | <30s | Event to enriched data |
| Dashboard load time | <3s | Initial dashboard render |
| Search query response | <2s | Elasticsearch query |
| Alert trigger time | <1min | Event to notification |
| Throughput | 1000 events/sec | Peak ingestion rate |

## Disaster Recovery

### Backup Strategy

**Databases**:
- PostgreSQL: Daily full backup, hourly incremental
- Point-in-time recovery (PITR) enabled
- Backups stored in S3 with versioning
- Cross-region replication for critical data

**Logs**:
- Elasticsearch snapshots daily
- Retention: 30 days in Elasticsearch, 90 days in S3
- Archival to cold storage after 90 days

**Configuration**:
- Version controlled in Git
- Automated backup on changes
- Infrastructure as Code (Terraform state)

### Recovery Procedures

**Service Failure**:
- Health checks detect failure
- Auto-restart via Docker/Kubernetes
- Alert if restart fails
- Failover to standby (if available)

**Data Corruption**:
- Restore from most recent backup
- PITR to specific timestamp if needed
- Validate data integrity post-restore
- Document incident for post-mortem

**Complete Disaster**:
- Use Terraform to rebuild infrastructure
- Restore databases from backups
- Redeploy application containers
- Restore configuration from Git
- Validate system end-to-end
- Target: RTO 4 hours, RPO 1 hour

## Monitoring Strategy

### Metrics (Prometheus)

**Infrastructure**:
- CPU, memory, disk, network utilization
- Container health and restarts
- Database connection pools
- Cache hit rates

**Application**:
- Request rates per honeypot service
- Error rates and types
- Processing latency (p50, p95, p99)
- Queue depths

**Business**:
- Attacks per hour/day
- Unique attacker IPs
- Credential pairs captured
- Commands executed

### Logs (Centralized)

- All application logs to Elasticsearch
- Structured JSON format
- Log levels: DEBUG, INFO, WARNING, ERROR
- Correlation IDs for request tracing
- Retention based on importance

### Alerts

**Critical** (immediate action):
- Service down >2 minutes
- Database unreachable
- Data pipeline stopped
- Disk >90% full

**Warning** (investigate soon):
- High error rate (>5%)
- Slow response times (>95th percentile)
- API rate limits approaching
- Cache hit rate <50%

**Info** (FYI):
- New attack patterns detected
- Unusual spike in traffic
- Known malicious IP detected

## Technology Decisions

### Why Python?

- **Pros**: Rich ecosystem, async support, rapid development
- **Cons**: Performance compared to compiled languages
- **Decision**: Use Python for most components, optimize hotspots if needed

### Why Elasticsearch?

- **Pros**: Full-text search, time-series optimization, scalability
- **Cons**: Memory hungry, operational complexity
- **Decision**: Benefits outweigh costs for log analysis use case

### Why PostgreSQL?

- **Pros**: ACID compliance, mature, powerful querying
- **Cons**: Scaling complexity for very large datasets
- **Decision**: Perfect for structured threat intel data

### Why Docker?

- **Pros**: Isolation, portability, easy deployment
- **Cons**: Overhead, networking complexity
- **Decision**: Essential for honeypot isolation and dev/prod parity

## Future Architecture Considerations

### Machine Learning Pipeline

```
Events → Feature Extraction → ML Model → Predictions
   ↓                              ↓
Training Data                  Anomalies/Classifications
```

**Use Cases**:
- Anomaly detection (unusual attack patterns)
- Attack classification (brute force, exploit, recon)
- Attacker clustering
- Predictive threat intelligence

### Distributed Honeypot Network

- Multiple geographic locations
- Centralized data aggregation
- Shared threat intelligence
- Coordinated response

### MISP Integration

- Automatic IOC extraction
- Bi-directional threat sharing
- STIX/TAXII support
- Community threat feeds

---

**Document Version**: 1.0
**Last Updated**: 2025-11-19
**Maintained By**: Architecture Team
**Next Review**: After Phase 2 completion
