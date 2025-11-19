#!/bin/bash
################################################################################
# HP_TI Security Testing Suite
#
# Performs automated security testing and vulnerability scanning.
#
# Usage: ./security_tests.sh [--quick|--full]
################################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
WARNINGS=0

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASSED++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAILED++)); }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((WARNINGS++)); }
log_info() { echo -e "[INFO] $1"; }

TEST_MODE="${1:---quick}"

echo "================================"
echo "HP_TI Security Testing Suite"
echo "Test mode: $TEST_MODE"
echo "Started: $(date)"
echo "================================"

################################################################################
# 1. Docker Security Tests
################################################################################

test_docker_security() {
    log_info "Testing Docker security configuration..."

    # Test 1: Containers not running as root
    log_info "Checking if containers run as non-root..."
    for container in $(docker ps --format "{{.Names}}"); do
        user=$(docker exec "$container" whoami 2>/dev/null || echo "root")
        if [[ "$user" == "root" ]]; then
            log_warn "Container $container is running as root"
        else
            log_pass "Container $container is running as $user"
        fi
    done

    # Test 2: Docker socket not mounted
    log_info "Checking Docker socket mounts..."
    if docker ps --format "{{.Mounts}}" | grep -q "/var/run/docker.sock"; then
        log_fail "Docker socket is mounted in container (security risk)"
    else
        log_pass "Docker socket not mounted in containers"
    fi

    # Test 3: Check for privileged containers
    log_info "Checking for privileged containers..."
    if docker ps --format "{{.Names}}\t{{.Privileged}}" | grep -q "true"; then
        log_fail "Privileged containers found"
    else
        log_pass "No privileged containers"
    fi

    # Test 4: Resource limits set
    log_info "Checking resource limits..."
    for container in $(docker ps --format "{{.Names}}"); do
        memory_limit=$(docker inspect "$container" | jq -r '.[0].HostConfig.Memory')
        cpu_limit=$(docker inspect "$container" | jq -r '.[0].HostConfig.CpuQuota')

        if [[ "$memory_limit" == "0" ]]; then
            log_warn "Container $container has no memory limit"
        else
            log_pass "Container $container has memory limit: $memory_limit bytes"
        fi
    done
}

################################################################################
# 2. Network Security Tests
################################################################################

test_network_security() {
    log_info "Testing network security..."

    # Test 1: Firewall active
    log_info "Checking firewall status..."
    if sudo ufw status | grep -q "Status: active"; then
        log_pass "Firewall is active"
    else
        log_fail "Firewall is not active"
    fi

    # Test 2: Only required ports open
    log_info "Checking open ports..."
    expected_ports=(22 2222 8080 8443 2323 2121)

    for port in "${expected_ports[@]}"; do
        if sudo ufw status | grep -q "$port"; then
            log_pass "Required port $port is open"
        else
            log_warn "Port $port may not be configured in firewall"
        fi
    done

    # Test 3: No unauthorized services listening
    log_info "Checking for unauthorized listening services..."
    listening=$(sudo netstat -tlnp | grep LISTEN || true)

    # Check for dangerous services
    if echo "$listening" | grep -q ":23 "; then
        log_fail "Telnet service detected (port 23)"
    fi

    if echo "$listening" | grep -q ":21 "; then
        log_fail "FTP service detected (port 21)"
    fi
}

################################################################################
# 3. SSH Security Tests
################################################################################

test_ssh_security() {
    log_info "Testing SSH security configuration..."

    # Test 1: Root login disabled
    if sudo sshd -T | grep -q "permitrootlogin no"; then
        log_pass "Root login disabled"
    else
        log_fail "Root login is enabled"
    fi

    # Test 2: Password authentication disabled
    if sudo sshd -T | grep -q "passwordauthentication no"; then
        log_pass "Password authentication disabled"
    else
        log_fail "Password authentication is enabled"
    fi

    # Test 3: Public key authentication enabled
    if sudo sshd -T | grep -q "pubkeyauthentication yes"; then
        log_pass "Public key authentication enabled"
    else
        log_fail "Public key authentication is not enabled"
    fi

    # Test 4: Protocol 2 only
    if sudo sshd -T | grep -q "protocol 2"; then
        log_pass "SSH Protocol 2 configured"
    else
        log_warn "SSH Protocol setting not found (may be using default)"
    fi
}

################################################################################
# 4. File Permission Tests
################################################################################

test_file_permissions() {
    log_info "Testing file permissions..."

    # Test 1: .env file permissions
    if [[ -f /opt/hp_ti/.env ]]; then
        perms=$(stat -c %a /opt/hp_ti/.env)
        if [[ "$perms" == "600" || "$perms" == "400" ]]; then
            log_pass ".env file has secure permissions ($perms)"
        else
            log_fail ".env file has insecure permissions ($perms)"
        fi
    else
        log_warn ".env file not found"
    fi

    # Test 2: Config directory permissions
    if [[ -d /opt/hp_ti/config ]]; then
        perms=$(stat -c %a /opt/hp_ti/config)
        if [[ "$perms" =~ ^7[0-5][0-5]$ ]]; then
            log_pass "Config directory has secure permissions ($perms)"
        else
            log_warn "Config directory permissions may be too open ($perms)"
        fi
    fi

    # Test 3: No world-writable files
    log_info "Checking for world-writable files..."
    world_writable=$(find /opt/hp_ti -type f -perm -002 2>/dev/null || true)
    if [[ -z "$world_writable" ]]; then
        log_pass "No world-writable files found"
    else
        log_fail "World-writable files found:\n$world_writable"
    fi
}

################################################################################
# 5. Secrets and Credentials Tests
################################################################################

test_secrets() {
    log_info "Testing secrets management..."

    # Test 1: No hardcoded credentials in code
    log_info "Checking for hardcoded credentials..."
    if grep -r "password.*=.*['\"]" /opt/hp_ti/honeypot/*.py 2>/dev/null | grep -v "getenv\|config"; then
        log_fail "Potential hardcoded passwords found in code"
    else
        log_pass "No hardcoded passwords found"
    fi

    # Test 2: No API keys in code
    if grep -r "api_key.*=.*['\"][a-zA-Z0-9]" /opt/hp_ti/honeypot/*.py 2>/dev/null | grep -v "getenv\|config"; then
        log_fail "Potential hardcoded API keys found in code"
    else
        log_pass "No hardcoded API keys found"
    fi

    # Test 3: .env in .gitignore
    if [[ -f /opt/hp_ti/.gitignore ]] && grep -q "^\.env$" /opt/hp_ti/.gitignore; then
        log_pass ".env is in .gitignore"
    else
        log_fail ".env is not in .gitignore"
    fi

    # Test 4: No secrets committed to git
    if git -C /opt/hp_ti log --all --full-history --source -- .env 2>/dev/null | grep -q ".env"; then
        log_fail ".env file found in git history"
    else
        log_pass "No .env in git history"
    fi
}

################################################################################
# 6. Database Security Tests
################################################################################

test_database_security() {
    log_info "Testing database security..."

    # Test 1: Database not publicly accessible
    if docker port hp_ti_postgres | grep -q "0.0.0.0:5432"; then
        log_fail "PostgreSQL is exposed to public network"
    else
        log_pass "PostgreSQL is not publicly exposed"
    fi

    # Test 2: Strong password policy (check length)
    db_password=$(grep DB_PASSWORD /opt/hp_ti/.env | cut -d'=' -f2)
    if [[ ${#db_password} -ge 20 ]]; then
        log_pass "Database password meets length requirement (>= 20 chars)"
    else
        log_fail "Database password is too short (< 20 chars)"
    fi

    # Test 3: SSL/TLS for connections (if configured)
    ssl_enabled=$(docker exec hp_ti_postgres psql -U hp_ti_user -d hp_ti_db -c "SHOW ssl;" 2>/dev/null | grep on || echo "off")
    if [[ "$ssl_enabled" == *"on"* ]]; then
        log_pass "Database SSL/TLS enabled"
    else
        log_warn "Database SSL/TLS not enabled"
    fi
}

################################################################################
# 7. Application Security Tests
################################################################################

test_application_security() {
    log_info "Testing application security..."

    # Test 1: Debug mode disabled in production
    if grep -q "DEBUG.*=.*false" /opt/hp_ti/.env 2>/dev/null; then
        log_pass "Debug mode is disabled"
    else
        log_fail "Debug mode may be enabled"
    fi

    # Test 2: Security headers present (if web interface exists)
    log_info "Checking HTTP security headers..."
    if curl -s -I http://localhost:8080 2>/dev/null | grep -q "X-Frame-Options"; then
        log_pass "X-Frame-Options header present"
    else
        log_warn "X-Frame-Options header missing"
    fi

    # Test 3: No SQL injection vulnerabilities (basic check)
    log_info "Checking for potential SQL injection patterns..."
    if grep -r "execute.*%.*%" /opt/hp_ti/honeypot/*.py 2>/dev/null; then
        log_fail "Potential SQL injection vulnerability found (string formatting in queries)"
    else
        log_pass "No obvious SQL injection patterns found"
    fi
}

################################################################################
# 8. Dependency Vulnerability Scan
################################################################################

test_dependencies() {
    if [[ "$TEST_MODE" == "--full" ]]; then
        log_info "Scanning dependencies for vulnerabilities..."

        # Python dependencies
        if command -v safety &> /dev/null; then
            log_info "Running safety check..."
            if safety check --json > /tmp/safety_report.json 2>&1; then
                log_pass "No known vulnerabilities in Python dependencies"
            else
                vulns=$(jq length /tmp/safety_report.json)
                log_fail "Found $vulns vulnerabilities in Python dependencies"
            fi
        else
            log_warn "safety not installed (pip install safety)"
        fi

        # Docker image vulnerabilities
        if command -v trivy &> /dev/null; then
            log_info "Scanning Docker images with Trivy..."
            for image in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep hp_ti); do
                if trivy image --severity HIGH,CRITICAL --quiet "$image" > /tmp/trivy_report.txt 2>&1; then
                    log_pass "No critical vulnerabilities in $image"
                else
                    log_fail "Vulnerabilities found in $image"
                fi
            done
        else
            log_warn "trivy not installed (recommended for production)"
        fi
    else
        log_info "Skipping dependency scan in quick mode (use --full)"
    fi
}

################################################################################
# 9. Logging and Monitoring Tests
################################################################################

test_logging() {
    log_info "Testing logging configuration..."

    # Test 1: Audit logging enabled
    if systemctl is-active --quiet auditd 2>/dev/null; then
        log_pass "Audit daemon is running"
    else
        log_warn "Audit daemon is not running"
    fi

    # Test 2: Logs being written
    if [[ -d /var/log/hp_ti ]] && [[ -n "$(ls -A /var/log/hp_ti 2>/dev/null)" ]]; then
        log_pass "Application logs are being written"
    else
        log_warn "No application logs found"
    fi

    # Test 3: Log rotation configured
    if [[ -f /etc/logrotate.d/hp_ti ]]; then
        log_pass "Log rotation configured"
    else
        log_warn "Log rotation not configured"
    fi
}

################################################################################
# 10. Compliance and Best Practices
################################################################################

test_compliance() {
    if [[ "$TEST_MODE" == "--full" ]]; then
        log_info "Running compliance checks..."

        # Run Lynis if available
        if command -v lynis &> /dev/null; then
            log_info "Running Lynis security audit..."
            sudo lynis audit system --quick --quiet > /tmp/lynis_report.txt 2>&1
            hardening_index=$(grep "Hardening index" /tmp/lynis_report.txt | awk '{print $4}')
            log_info "System hardening index: $hardening_index"

            if [[ ${hardening_index%.*} -ge 70 ]]; then
                log_pass "System hardening index is good ($hardening_index)"
            else
                log_warn "System hardening index could be improved ($hardening_index)"
            fi
        else
            log_warn "lynis not installed (recommended for compliance)"
        fi
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    test_docker_security
    test_network_security
    test_ssh_security
    test_file_permissions
    test_secrets
    test_database_security
    test_application_security
    test_dependencies
    test_logging
    test_compliance

    # Print summary
    echo ""
    echo "================================"
    echo "Security Test Summary"
    echo "================================"
    echo -e "${GREEN}Passed:${NC}   $PASSED"
    echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
    echo -e "${RED}Failed:${NC}   $FAILED"
    echo "================================"

    # Exit code
    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}Security tests FAILED${NC}"
        echo "Please address the failed tests before deploying to production."
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Security tests passed with warnings${NC}"
        echo "Review warnings and address if necessary."
        exit 0
    else
        echo -e "${GREEN}All security tests PASSED${NC}"
        exit 0
    fi
}

# Run main
main "$@"
