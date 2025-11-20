# HP_TI Grafana Dashboards

This directory contains pre-configured Grafana dashboards for monitoring the HP_TI honeypot and threat intelligence platform.

## Available Dashboards

### 1. Overview Dashboard (`overview.json`)
**Purpose**: High-level view of honeypot activity

**Panels**:
- Total Connections (24h)
- Authentication Attempts (24h)
- Attacks Detected (24h)
- Unique Attackers (24h)
- Connections by Service (timeline)
- Attack Types Distribution (pie chart)
- Authentication Attempts Timeline
- Top Attacking Countries (bar chart)
- Active Sessions (timeline)
- Service Health (status)

**Use Case**: Executive overview, daily monitoring, system health checks

---

### 2. Attack Analysis Dashboard (`attack_analysis.json`)
**Purpose**: Deep dive into attack patterns and techniques

**Panels**:
- Attack Rate Over Time (timeline with attack types)
- HTTP Attack Vectors (pie chart)
- Top Malicious Commands (table)
- Commands Executed Over Time (bar chart)
- Attack Patterns Detected (timeline)
- FTP Operations (bar chart)
- Unique Credentials Captured (stat)
- Attack Success Rate (gauge)

**Use Case**: Threat analysis, attack research, incident investigation

---

### 3. Pipeline Health Dashboard (`pipeline_health.json`)
**Purpose**: Monitor data processing pipeline performance

**Panels**:
- Events Processed Rate (by stage)
- Event Processing Success Rate (gauge)
- Processing Duration by Stage (p50, p95)
- Queue Sizes (timeline)
- Storage Write Rate (by backend)
- Storage Write Errors (with alerts)
- Enrichment API Calls (by provider and status)
- Enrichment Cache Hit Rate (gauge)
- Database Connection Pool (stacked timeline)
- Worker Activity (timeline)

**Use Case**: Performance monitoring, troubleshooting, capacity planning

---

## Installation

### Method 1: Import via Grafana UI

1. Access your Grafana instance (default: http://localhost:3000)
2. Login with admin credentials (default: admin/admin)
3. Go to **Dashboards** → **Import**
4. Click **Upload JSON file**
5. Select one of the dashboard JSON files
6. Click **Import**
7. Repeat for each dashboard

### Method 2: Automated Import with Docker

Dashboards can be automatically imported when using Docker Compose:

1. Ensure your `docker-compose.yml` includes the Grafana volume mount:
   ```yaml
   grafana:
     volumes:
       - ./visualization/dashboards:/etc/grafana/provisioning/dashboards:ro
   ```

2. Create a provisioning config file at `visualization/dashboards/dashboard_provider.yml`:
   ```yaml
   apiVersion: 1
   providers:
     - name: 'HP_TI Dashboards'
       orgId: 1
       folder: 'HP_TI'
       type: file
       disableDeletion: false
       updateIntervalSeconds: 10
       allowUiUpdates: true
       options:
         path: /etc/grafana/provisioning/dashboards
   ```

3. Restart Grafana:
   ```bash
   docker-compose restart grafana
   ```

### Method 3: API Import (for CI/CD)

```bash
# Set variables
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"

# Import dashboard
for dashboard in overview attack_analysis pipeline_health; do
  curl -X POST \
    -H "Content-Type: application/json" \
    -d @"${dashboard}.json" \
    "http://${GRAFANA_USER}:${GRAFANA_PASSWORD}@${GRAFANA_URL}/api/dashboards/db"
done
```

---

## Configuration

### Data Source Setup

Before importing dashboards, configure the Prometheus data source:

1. Go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - Name: `Prometheus`
   - URL: `http://prometheus:9090` (Docker) or `http://localhost:9090` (local)
   - Access: `Server`
5. Click **Save & Test**

### Dashboard Variables

Each dashboard includes template variables for filtering:

**Overview Dashboard**:
- `service`: Filter by honeypot service (ssh, http, telnet, ftp)

**Attack Analysis Dashboard**:
- `time_range`: Quick time range selection
- `service`: Filter by service

**Pipeline Health Dashboard**:
- `backend`: Filter by storage backend (postgres, elasticsearch)

---

## Customization

### Modifying Dashboards

1. Open the dashboard in Grafana
2. Click the **gear icon** (Dashboard settings)
3. Make your changes
4. Click **Save dashboard**
5. To export: **Share** → **Export** → **Save to file**

### Adding Panels

1. Click **Add panel** in dashboard edit mode
2. Configure visualization and query
3. Common queries:
   ```promql
   # Connection rate by service
   sum(rate(honeypot_connections_total[5m])) by (service)

   # Attack detection rate
   sum(rate(honeypot_attacks_total[5m])) by (attack_type)

   # Pipeline processing latency
   histogram_quantile(0.95, sum(rate(pipeline_processing_duration_seconds_bucket[5m])) by (le))
   ```

### Alert Rules

To add alerts to panels:

1. Edit the panel
2. Go to **Alert** tab
3. Click **Create Alert**
4. Configure conditions:
   ```
   WHEN avg() OF query(A, 5m, now) IS ABOVE 100
   ```
5. Set notification channel

---

## Metrics Reference

### Honeypot Metrics

```promql
# Connections
honeypot_connections_total{service, status}
honeypot_connections_active{service}
honeypot_connection_duration_seconds{service}

# Authentication
honeypot_auth_attempts_total{service, success}
honeypot_unique_credentials{service}

# Attacks
honeypot_attacks_total{service, attack_type}
honeypot_attack_sources{service}

# Sessions
honeypot_sessions_total{service}
honeypot_sessions_active{service}

# HTTP-specific
honeypot_http_requests_total{method, path, status_code}
honeypot_http_attack_vectors{vector}

# FTP-specific
honeypot_ftp_operations_total{operation}
```

### Pipeline Metrics

```promql
# Events
pipeline_events_processed_total{stage, source}
pipeline_events_failed_total{stage, error_type}

# Processing
pipeline_processing_duration_seconds{stage}
pipeline_queue_size{queue_name}

# Storage
pipeline_storage_writes_total{backend, operation}
pipeline_storage_write_errors_total{backend, error_type}

# Enrichment
pipeline_enrichment_api_calls_total{provider, status}
pipeline_enrichment_cache_hits_total{enricher}
pipeline_enrichment_cache_misses_total{enricher}
```

---

## Troubleshooting

### Dashboard Shows "No Data"

1. **Check Prometheus**:
   ```bash
   curl http://localhost:9090/api/v1/query?query=up
   ```

2. **Verify metrics are being exported**:
   ```bash
   curl http://localhost:9090/metrics | grep honeypot
   ```

3. **Check data source connection** in Grafana settings

### Slow Dashboard Performance

1. **Reduce time range**: Use shorter time ranges for large datasets
2. **Increase refresh interval**: Change from 30s to 1m or 5m
3. **Optimize queries**: Use recording rules for complex queries
4. **Enable query caching** in Prometheus

### Missing Panels

1. **Check Grafana version**: Dashboards require Grafana 8.0+
2. **Update panel plugin**: Some panels require specific plugins
3. **Review browser console**: Check for JavaScript errors

---

## Best Practices

### Dashboard Organization

1. **Create folders** for different dashboard categories
2. **Use consistent naming** conventions
3. **Document custom dashboards** with descriptions
4. **Version control** dashboard JSON files

### Query Optimization

1. **Use recording rules** for frequently used queries:
   ```yaml
   # prometheus.yml
   rule_files:
     - 'recording_rules.yml'
   ```

2. **Limit cardinality** of labels:
   - Avoid high-cardinality labels (like IP addresses)
   - Use aggregation where possible

3. **Set appropriate scrape intervals**:
   ```yaml
   # prometheus.yml
   scrape_configs:
     - job_name: 'honeypot'
       scrape_interval: 30s
   ```

### Alert Configuration

1. **Set meaningful thresholds** based on baseline
2. **Avoid alert fatigue** with proper grouping
3. **Test alerts** before deploying to production
4. **Document alert runbooks**

---

## Additional Resources

- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [HP_TI Metrics Documentation](../../docs/METRICS.md)
- [HP_TI Architecture](../../docs/architecture/ARCHITECTURE.md)

---

**Last Updated**: 2025-01-15
**Version**: Phase 5 - Visualization & Alerting
