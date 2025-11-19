#!/bin/bash
################################################################################
# HP_TI Health Check Script
#
# Verifies system health before and after deployment.
#
# Usage: ./health_check.sh [--pre-deploy|--post-deploy]
################################################################################

set -euo pipefail

CHECK_TYPE="${1:---post-deploy}"
FAILED=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
    if eval "$2"; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        ((FAILED++))
    fi
}

echo "Running HP_TI Health Checks ($CHECK_TYPE)..."

# Check Docker is running
check "Docker daemon" "docker info > /dev/null 2>&1"

# Check services are running
check "Honeypot container" "docker ps | grep -q hp_ti_honeypot"
check "PostgreSQL container" "docker ps | grep -q hp_ti_postgres"
check "Elasticsearch container" "docker ps | grep -q hp_ti_elasticsearch"
check "Redis container" "docker ps | grep -q hp_ti_redis"

# Check service endpoints
if [[ "$CHECK_TYPE" == "--post-deploy" ]]; then
    check "Honeypot SSH service" "nc -z localhost 2222"
    check "Honeypot HTTP service" "nc -z localhost 8080"
    check "Metrics endpoint" "curl -sf http://localhost:9090/metrics > /dev/null"
    check "PostgreSQL connection" "docker exec hp_ti_postgres pg_isready -U hp_ti_user"
    check "Elasticsearch health" "curl -sf http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\\|yellow\"'"
    check "Redis ping" "docker exec hp_ti_redis redis-cli ping | grep -q PONG"
fi

# Check disk space
check "Disk space (> 20% free)" "[[ \$(df / | tail -1 | awk '{print \$5}' | sed 's/%//') -lt 80 ]]"

# Check memory
check "Memory available" "[[ \$(free | grep Mem | awk '{print (\$7/\$2)*100}' | cut -d. -f1) -gt 10 ]]"

echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All health checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED health check(s) failed!${NC}"
    exit 1
fi
