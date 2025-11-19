## HP_TI Threat Intelligence Documentation

## Overview

The HP_TI threat intelligence system enriches honeypot data with external threat intelligence sources, providing context about attackers, their origins, reputation, and patterns.

## Architecture

```
IP Address → Enrichment Manager → [GeoIP, AbuseIPDB, WHOIS] → Enriched Data
                                              ↓
                                          Redis Cache
                                              ↓
                                        PostgreSQL Storage
```

## Components

### 1. Cache Manager (`threat_intel/enrichment/cache_manager.py`)

Redis-based caching to reduce API calls and improve performance.

**Features**:
- TTL-based caching per enrichment source
- Automatic expiration (7 days for GeoIP, 6 hours for AbuseIPDB)
- Cache statistics and hit rate tracking
- Bulk cache warming
- Prefix-based cache flushing

**Usage**:
```python
from threat_intel.enrichment.cache_manager import CacheManager

cache = CacheManager(redis_url="redis://localhost:6379/0")

# Set cached data
cache.set("geoip", "192.168.1.1", {"country": "US"})

# Get cached data
data = cache.get("geoip", "192.168.1.1")

# Get cache statistics
stats = cache.get_stats()
# Returns: hits, misses, hit_rate, memory_used_mb, total_keys
```

### 2. Base Enricher (`threat_intel/enrichment/base_enricher.py`)

Abstract base class for all enrichers with common functionality.

**Features**:
- Automatic caching
- Rate limiting (requests per minute)
- Error handling
- Result metadata (cached, timestamp, error)

**Creating Custom Enrichers**:
```python
from threat_intel.enrichment.base_enricher import BaseEnricher

class MyEnricher(BaseEnricher):
    def __init__(self, cache_manager):
        super().__init__(
            name="my_enricher",
            cache_manager=cache_manager,
            rate_limit=60,  # 60 requests per minute
            enabled=True
        )

    def _enrich_impl(self, identifier: str, **kwargs):
        # Implement enrichment logic
        return {"data": "enriched_value"}
```

### 3. GeoIP Enricher (`threat_intel/enrichment/geoip_enricher.py`)

Provides geolocation data using MaxMind GeoLite2 database.

**Features**:
- Country, city, coordinates
- Timezone information
- ISP and organization data
- No API calls (local database)
- No rate limiting needed

**Data Returned**:
```json
{
  "country_code": "US",
  "country_name": "United States",
  "city": "New York",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "timezone": "America/New_York",
  "accuracy_radius": 5
}
```

**Setup**:
```bash
# Download GeoLite2-City database
wget https://download.maxmind.com/app/geoip_download?...
mv GeoLite2-City.mmdb data/
```

```python
enricher = GeoIPEnricher(
    cache_manager=cache,
    database_path="data/GeoLite2-City.mmdb",
    enabled=True
)

result = enricher.enrich("8.8.8.8")
```

### 4. AbuseIPDB Enricher (`threat_intel/enrichment/abuseipdb_enricher.py`)

Queries AbuseIPDB for IP reputation and abuse reports.

**Features**:
- Abuse confidence score (0-100)
- Report history
- Threat level classification
- Automatic rate limiting (4 requests/minute)
- Report submission capability

**Data Returned**:
```json
{
  "abuse_confidence_score": 75,
  "threat_level": "critical",
  "country_code": "CN",
  "isp": "ChinaNet",
  "is_whitelisted": false,
  "total_reports": 42,
  "num_distinct_users": 15,
  "last_reported_at": "2025-11-19T10:30:00Z",
  "recent_reports": [...]
}
```

**Threat Levels**:
- **critical**: score >= 75
- **high**: score >= 50
- **medium**: score >= 25
- **low**: score < 25

**Usage**:
```python
enricher = AbuseIPDBEnricher(
    cache_manager=cache,
    api_key="your_api_key",
    enabled=True
)

# Check IP
result = enricher.enrich("1.2.3.4")

# Report IP (honeypot detected brute force)
enricher.report_ip(
    ip_address="1.2.3.4",
    categories=[18, 22],  # Brute Force, SSH
    comment="SSH brute force attack, 50 attempts"
)
```

**API Key**: Get from https://www.abuseipdb.com/api

**Rate Limits** (Free Tier):
- 1000 requests/day
- 4 requests/minute

### 5. WHOIS Enricher (`threat_intel/enrichment/whois_enricher.py`)

Provides ASN and organization data using WHOIS queries.

**Features**:
- ASN (Autonomous System Number)
- BGP prefix
- Organization/ISP name
- Country and registry
- Team Cymru integration for fast lookups

**Data Returned**:
```json
{
  "asn": 15169,
  "asn_name": "GOOGLE",
  "bgp_prefix": "8.8.8.0/24",
  "country_code": "US",
  "registry": "arin",
  "allocated": "2014-03-14"
}
```

**Usage**:
```python
enricher = WHOISEnricher(
    cache_manager=cache,
    enabled=True
)

result = enricher.enrich("8.8.8.8")
```

### 6. Enrichment Manager (`threat_intel/enrichment/enrichment_manager.py`)

Coordinates multiple enrichment sources with parallel execution.

**Features**:
- Runs enrichers in parallel
- Calculates confidence scores
- Manages all enrichment sources
- Batch enrichment support
- Async enrichment

**Usage**:
```python
from threat_intel.enrichment.enrichment_manager import EnrichmentManager

manager = EnrichmentManager(
    cache_manager=cache,
    geoip_db_path="data/GeoLite2-City.mmdb",
    abuseipdb_api_key="your_key",
    max_workers=5  # Parallel workers
)

# Enrich single IP (parallel)
result = manager.enrich_ip("1.2.3.4")

# Enrich specific sources only
result = manager.enrich_ip("1.2.3.4", sources=["geoip", "whois"])

# Batch enrichment
results = manager.enrich_batch(["1.2.3.4", "5.6.7.8", "9.10.11.12"])

# Async enrichment
result = await manager.enrich_ip_async("1.2.3.4")
```

**Enrichment Result**:
```json
{
  "ip_address": "1.2.3.4",
  "enrichments": {
    "geoip": {
      "source": "geoip",
      "data": {...},
      "cached": false,
      "timestamp": "2025-11-19T12:30:45Z"
    },
    "abuseipdb": {
      "source": "abuseipdb",
      "data": {...},
      "cached": true,
      "timestamp": "2025-11-19T12:30:45Z"
    },
    "whois": {
      "source": "whois",
      "data": {...},
      "cached": false,
      "timestamp": "2025-11-19T12:30:45Z"
    }
  },
  "confidence_score": 75.5,
  "timestamp": "2025-11-19T12:30:45Z"
}
```

### 7. Pattern Detector (`threat_intel/correlators/pattern_detector.py`)

Detects attack patterns and correlates events.

**Detected Patterns**:
1. **Brute Force**: Multiple auth attempts from single IP
2. **Credential Stuffing**: Many unique credentials, few retries each
3. **Reconnaissance**: Information gathering commands
4. **Automated Tools**: Signatures of Metasploit, nmap, etc.
5. **Distributed Attacks**: Same credentials from multiple IPs

**Usage**:
```python
from threat_intel.correlators.pattern_detector import PatternDetector

detector = PatternDetector(time_window=600)  # 10 minute window

# Analyze single session
patterns = detector.analyze_session(session_data)

# Detect distributed attacks
pattern = detector.detect_distributed_attack(list_of_sessions)

for pattern in patterns:
    print(f"Type: {pattern.pattern_type}")
    print(f"Severity: {pattern.severity}")
    print(f"Confidence: {pattern.confidence_score}%")
    print(f"Description: {pattern.description}")
```

**Pattern Object**:
```python
AttackPattern(
    pattern_type="brute_force",
    severity="high",
    description="Brute force attack from 1.2.3.4 with 50 attempts",
    indicators={
        "source_ip": "1.2.3.4",
        "attempt_count": 50,
        "unique_credentials": 25,
        "attempt_rate_per_second": 2.5
    },
    first_seen=datetime(...),
    last_seen=datetime(...),
    occurrence_count=50,
    confidence_score=100.0
)
```

## Integration Example

Complete workflow integrating enrichment with storage:

```python
from pipeline.storage.postgres_client import PostgreSQLClient
from pipeline.storage.storage_manager import StorageManager
from threat_intel.enrichment.cache_manager import CacheManager
from threat_intel.enrichment.enrichment_manager import EnrichmentManager
from threat_intel.correlators.pattern_detector import PatternDetector

# Initialize components
cache = CacheManager(redis_url="redis://localhost:6379/0")
postgres = PostgreSQLClient(database_url="postgresql://...")
enrichment = EnrichmentManager(
    cache_manager=cache,
    geoip_db_path="data/GeoLite2-City.mmdb",
    abuseipdb_api_key="your_key"
)
detector = PatternDetector()

# Process new session
def process_session(session_data):
    source_ip = session_data["source_ip"]

    # 1. Enrich IP
    enriched = enrichment.enrich_ip(source_ip)

    # 2. Store enrichment data
    postgres.upsert_ip_intelligence(source_ip, {
        "country_code": enriched["enrichments"]["geoip"]["data"].get("country_code"),
        "abuse_confidence_score": enriched["enrichments"]["abuseipdb"]["data"].get("abuse_confidence_score"),
        "asn": enriched["enrichments"]["whois"]["data"].get("asn"),
        "threat_level": enriched["enrichments"]["abuseipdb"]["data"].get("threat_level"),
        "enrichment_data": enriched
    })

    # 3. Detect patterns
    patterns = detector.analyze_session(session_data)

    # 4. Store patterns
    for pattern in patterns:
        postgres.create_attack_pattern({
            "pattern_type": pattern.pattern_type,
            "severity": pattern.severity,
            "description": pattern.description,
            "indicators": pattern.indicators,
            "confidence_score": pattern.confidence_score
        })

    return enriched, patterns
```

## Configuration

### Environment Variables

Add to `.env`:
```bash
# GeoIP
MAXMIND_ENABLED=true
MAXMIND_DB_PATH=./data/GeoLite2-City.mmdb
MAXMIND_CACHE_TTL=604800  # 7 days

# AbuseIPDB
ABUSEIPDB_API_KEY=your_api_key_here
ABUSEIPDB_ENABLED=true
ABUSEIPDB_RATE_LIMIT=1000
ABUSEIPDB_CACHE_TTL=21600  # 6 hours

# WHOIS
WHOIS_ENABLED=true
WHOIS_CACHE_TTL=604800  # 7 days

# Redis Cache
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=86400
REDIS_MAX_CONNECTIONS=50
```

## Performance

### Caching Strategy

| Source | TTL | Rationale |
|--------|-----|-----------|
| GeoIP | 7 days | Geolocation rarely changes |
| WHOIS | 7 days | ASN/org rarely changes |
| AbuseIPDB | 6 hours | Reputation changes frequently |

### Expected Response Times

| Operation | Time | Notes |
|-----------|------|-------|
| GeoIP lookup | <10ms | Local database |
| Cached lookup | <5ms | Redis |
| AbuseIPDB API | 200-500ms | Network dependent |
| WHOIS query | 100-300ms | Network dependent |
| Parallel enrichment (all 3) | ~500ms | Fastest source determines time |

### Rate Limiting

Configured to respect API limits:
- **AbuseIPDB**: 4 requests/minute (free tier)
- **WHOIS**: 30 requests/minute (courtesy limit)
- **GeoIP**: No limit (local)

## Monitoring

### Cache Statistics

```python
stats = cache.get_stats()
# {
#     "total_keys": 1500,
#     "hits": 8500,
#     "misses": 1500,
#     "hit_rate": 85.0,
#     "memory_used_mb": 45.2
# }
```

### Enrichment Statistics

```python
stats = enrichment_manager.get_enricher_stats()
# {
#     "geoip": {"cached_entries": 500, "enabled": true},
#     "abuseipdb": {"cached_entries": 300, "enabled": true},
#     "whois": {"cached_entries": 450, "enabled": true},
#     "overall_cache": {...}
# }
```

## Troubleshooting

### GeoIP Database Not Found

```
ERROR: GeoIP database not found: ./data/GeoLite2-City.mmdb
```

**Solution**:
1. Download from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
2. Extract to `data/` directory
3. Verify path in `.env`

### AbuseIPDB Rate Limit

```
WARNING: AbuseIPDB rate limit exceeded
```

**Solution**:
- Increase cache TTL to reduce requests
- Upgrade to paid tier for higher limits
- Implement request queuing

### Redis Connection Error

```
ERROR: Failed to connect to Redis: ConnectionRefusedError
```

**Solution**:
```bash
# Start Redis
docker-compose up -d redis

# Or install locally
sudo systemctl start redis
```

## Best Practices

1. **Always Cache**: Enable caching to minimize API costs
2. **Batch Operations**: Enrich multiple IPs together
3. **Monitor Costs**: Track API usage and stay within limits
4. **Update GeoIP**: Update MaxMind database monthly
5. **Validate IPs**: Skip private/loopback IPs
6. **Handle Errors**: Enrichment failures shouldn't block storage
7. **Set Alerts**: Alert on high cache miss rates

## Next Steps

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for Phase 4:
- Additional honeypot services (HTTP, Telnet, FTP)
- Multi-service enrichment
- Cross-service correlation
- Advanced pattern detection
