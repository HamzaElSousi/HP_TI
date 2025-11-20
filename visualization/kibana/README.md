# HP_TI Kibana Integration

This directory contains Kibana configurations for log exploration, searching, and visualization of honeypot data stored in Elasticsearch.

## Overview

Kibana provides a powerful interface for:
- Full-text log search
- Real-time log exploration
- Custom visualizations
- Saved searches and queries
- Drill-down analysis

## Index Patterns

### hp_ti_logs-*
**Purpose**: All honeypot logs (SSH, HTTP, Telnet, FTP)

**Fields**:
- `@timestamp`: Event timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `component`: Service component (ssh_honeypot, http_honeypot, etc.)
- `event_type`: Event type (connection, auth_attempt, command, attack, etc.)
- `source_ip`: Attacker IP address
- `session_id`: Unique session identifier
- `service`: Honeypot service (ssh, http, telnet, ftp)
- `username`: Authentication username
- `password`: Authentication password
- `command`: Executed command
- `attack_type`: Detected attack type
- `http.method`: HTTP request method
- `http.path`: HTTP request path
- `http.status_code`: HTTP response code
- `geo.country`: Country code
- `geo.city`: City name
- `threat_intel.score`: Threat intelligence score
- `metadata.*`: Additional metadata fields

### hp_ti_metrics-*
**Purpose**: System and pipeline metrics

**Fields**:
- `@timestamp`: Metric timestamp
- `metric_type`: Type of metric
- `service`: Related service
- `value`: Metric value
- `tags`: Metric tags

## Saved Searches

### 1. Recent Authentication Attempts
```
component:ssh_honeypot AND event_type:auth_attempt
```
Sort by: `@timestamp` (descending)
Time range: Last 24 hours

### 2. Failed Attacks by IP
```
event_type:attack AND attack_type:*
```
Aggregation: Terms on `source_ip`
Time range: Last 7 days

### 3. Malicious Commands
```
event_type:command AND malicious:true
```
Sort by: `@timestamp` (descending)
Time range: Last 24 hours

### 4. HTTP Attacks
```
component:http_honeypot AND event_type:attack
```
Aggregation: Terms on `attack_type`
Time range: Last 24 hours

### 5. High Threat Score IPs
```
threat_intel.score:>=80
```
Sort by: `threat_intel.score` (descending)
Time range: Last 7 days

## Visualizations

### Connections Over Time
- **Type**: Line chart
- **Metrics**: Count
- **Buckets**: Date Histogram on `@timestamp`
- **Split Series**: Terms on `service`

### Attack Types Distribution
- **Type**: Pie chart
- **Metrics**: Count
- **Buckets**: Terms on `attack_type`

### Geographic Heat Map
- **Type**: Coordinate map
- **Metrics**: Count
- **Buckets**: Geohash on `geo.location`

### Top Attacking Countries
- **Type**: Horizontal bar chart
- **Metrics**: Count
- **Buckets**: Terms on `geo.country`

### Authentication Attempts Timeline
- **Type**: Vertical bar chart
- **Metrics**: Count
- **Buckets**: Date Histogram on `@timestamp`
- **Split Series**: Terms on `service`

### Top Usernames
- **Type**: Data table
- **Metrics**: Count
- **Buckets**: Terms on `username`

### Top Commands
- **Type**: Tag cloud
- **Metrics**: Count
- **Buckets**: Terms on `command`

### Service Health
- **Type**: Metric
- **Metrics**: Unique count of `session_id` per service

## Setup Instructions

### 1. Create Index Pattern

1. Access Kibana: `http://localhost:5601`
2. Go to **Management** → **Stack Management** → **Index Patterns**
3. Click **Create index pattern**
4. Enter pattern: `hp_ti_logs-*`
5. Select time field: `@timestamp`
6. Click **Create**

### 2. Import Saved Searches

1. Go to **Management** → **Saved Objects**
2. Click **Import**
3. Select `saved_searches.ndjson`
4. Click **Import**

### 3. Import Visualizations

1. Go to **Management** → **Saved Objects**
2. Click **Import**
3. Select `visualizations.ndjson`
4. Click **Import**

### 4. Create Dashboard

1. Go to **Dashboard** → **Create dashboard**
2. Click **Add from library**
3. Add desired visualizations
4. Arrange and resize panels
5. Click **Save**

## Common Queries

### Find Brute Force Attacks
```
event_type:auth_attempt AND source_ip:*
| stats count by source_ip
| where count > 50
```

### Find SQL Injection Attempts
```
component:http_honeypot AND (
  http.path:*UNION* OR
  http.path:*SELECT* OR
  http.query:*' OR '1'='1*
)
```

### Find New IPs
```
NOT threat_intel.first_seen:<now-24h
```

### Find Commands with Malware URLs
```
command:*wget* OR command:*curl* OR command:*/bin/sh*
```

### Find Coordinated Attacks
```
event_type:auth_attempt
| stats dc(source_ip) as ip_count by username, password
| where ip_count > 5
```

## Discovery Best Practices

### 1. Time Range Selection
- Use **Quick select** for common ranges (Last 15 minutes, Last 24 hours, etc.)
- Use **Absolute** for specific time ranges
- Use **Relative** for rolling time windows

### 2. Field Filters
- Click on field values to add filters
- Use **+** to include, **-** to exclude
- Combine multiple filters with AND/OR logic

### 3. Saved Searches
- Save frequently used queries
- Share searches with team members
- Create search alerts for important patterns

### 4. Performance Tips
- Limit time range for large datasets
- Use filters instead of query strings when possible
- Aggregate before visualizing large datasets
- Use index patterns with date ranges

## Alerting

### Create Alert in Kibana

1. Go to **Stack Management** → **Rules and Connectors**
2. Click **Create rule**
3. Select **Index threshold**
4. Configure:
   - Index pattern: `hp_ti_logs-*`
   - Time field: `@timestamp`
   - Aggregation: Count
   - Condition: Above threshold
5. Add actions (email, webhook, etc.)
6. Click **Save**

### Example Alert Rules

**High Authentication Failure Rate**:
- Threshold: > 100 attempts in 5 minutes
- Condition: `event_type:auth_attempt AND success:false`
- Action: Send email to security team

**New Attack Type Detected**:
- Threshold: Any new value
- Condition: `event_type:attack`
- Field: `attack_type`
- Action: Slack notification

**Service Down**:
- Threshold: Count = 0
- Condition: `component:*_honeypot`
- Time window: 5 minutes
- Action: PagerDuty alert

## Troubleshooting

### No Data Appearing

1. **Check index pattern**: Verify `hp_ti_logs-*` matches your indices
2. **Check time range**: Ensure time range includes your data
3. **Verify data ingestion**: Check Elasticsearch indices exist
4. **Refresh field list**: Go to Index Pattern settings → Refresh

### Slow Queries

1. **Reduce time range**: Search shorter time periods
2. **Add more filters**: Narrow down results before visualizing
3. **Use aggregations**: Aggregate data before visualization
4. **Optimize index**: Ensure proper index settings

### Visualization Not Loading

1. **Check query**: Verify Lucene query syntax
2. **Check aggregations**: Ensure aggregation fields exist
3. **Reduce data size**: Limit buckets/results
4. **Clear cache**: Browser cache and Kibana cache

## Integration with HP_TI

### Automatic Log Shipping

Logs are automatically shipped to Elasticsearch via:
- Direct writes from Python Elasticsearch client
- Structured JSON log format
- Index rotation (daily/weekly)
- Index lifecycle management

### Index Lifecycle Management

- **Hot**: Last 7 days (optimized for writes)
- **Warm**: 7-30 days (optimized for reads)
- **Cold**: 30-90 days (compressed storage)
- **Delete**: After 90 days (configurable)

## Additional Resources

- [Kibana Documentation](https://www.elastic.co/guide/en/kibana/current/index.html)
- [Lucene Query Syntax](https://www.elastic.co/guide/en/kibana/current/lucene-query.html)
- [KQL (Kibana Query Language)](https://www.elastic.co/guide/en/kibana/current/kuery-query.html)
- [Kibana Visualizations](https://www.elastic.co/guide/en/kibana/current/dashboard.html)

---

**Last Updated**: 2025-01-15
**Version**: Phase 5 - Visualization & Alerting
