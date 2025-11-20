#!/bin/bash
################################################################################
# HP_TI Security Hardening Script
#
# This script automates security hardening for HP_TI deployment.
# Run with sudo/root privileges.
#
# Usage: sudo ./hardening_script.sh [--production|--staging|--dev]
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Environment (default to production)
ENVIRONMENT="${1:---production}"

# Logging
LOG_FILE="/var/log/hp_ti_hardening_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
}

################################################################################
# System Updates
################################################################################

update_system() {
    log "Updating system packages..."

    if command -v apt-get &> /dev/null; then
        apt-get update -y
        apt-get upgrade -y
        apt-get autoremove -y
    elif command -v yum &> /dev/null; then
        yum update -y
        yum autoremove -y
    else
        warn "Unknown package manager, skipping system updates"
    fi
}

################################################################################
# Firewall Configuration
################################################################################

configure_firewall() {
    log "Configuring firewall..."

    if command -v ufw &> /dev/null; then
        # UFW (Ubuntu/Debian)
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing

        # Allow SSH (management)
        ufw allow 22/tcp comment 'SSH Management'

        # Allow honeypot services
        ufw allow 2222/tcp comment 'SSH Honeypot'
        ufw allow 8080/tcp comment 'HTTP Honeypot'
        ufw allow 8443/tcp comment 'HTTPS Honeypot'
        ufw allow 2323/tcp comment 'Telnet Honeypot'
        ufw allow 2121/tcp comment 'FTP Honeypot'

        # Allow monitoring endpoints (restrict to internal network in production)
        if [[ "$ENVIRONMENT" == "--production" ]]; then
            warn "Metrics endpoint should be restricted to internal network only"
            # ufw allow from 10.0.0.0/8 to any port 9090 comment 'Prometheus Metrics'
        else
            ufw allow 9090/tcp comment 'Prometheus Metrics (Dev)'
        fi

        ufw --force enable
        log "UFW firewall configured"

    elif command -v firewall-cmd &> /dev/null; then
        # firewalld (RHEL/CentOS)
        systemctl enable --now firewalld

        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-port=2222/tcp  # SSH Honeypot
        firewall-cmd --permanent --add-port=8080/tcp  # HTTP Honeypot
        firewall-cmd --permanent --add-port=8443/tcp  # HTTPS Honeypot
        firewall-cmd --permanent --add-port=2323/tcp  # Telnet Honeypot
        firewall-cmd --permanent --add-port=2121/tcp  # FTP Honeypot

        if [[ "$ENVIRONMENT" != "--production" ]]; then
            firewall-cmd --permanent --add-port=9090/tcp  # Metrics (Dev only)
        fi

        firewall-cmd --reload
        log "firewalld configured"
    else
        warn "No supported firewall found, skipping firewall configuration"
    fi
}

################################################################################
# SSH Hardening
################################################################################

harden_ssh() {
    log "Hardening SSH configuration..."

    SSH_CONFIG="/etc/ssh/sshd_config"

    if [[ ! -f "$SSH_CONFIG.backup" ]]; then
        cp "$SSH_CONFIG" "$SSH_CONFIG.backup"
    fi

    # Disable root login
    sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' "$SSH_CONFIG"

    # Disable password authentication (use keys only)
    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' "$SSH_CONFIG"
    sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSH_CONFIG"

    # Disable empty passwords
    sed -i 's/^#*PermitEmptyPasswords.*/PermitEmptyPasswords no/' "$SSH_CONFIG"

    # Use Protocol 2
    if ! grep -q "^Protocol 2" "$SSH_CONFIG"; then
        echo "Protocol 2" >> "$SSH_CONFIG"
    fi

    # Set max auth tries
    sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' "$SSH_CONFIG"

    # Disable X11 forwarding
    sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' "$SSH_CONFIG"

    # Set ClientAliveInterval
    sed -i 's/^#*ClientAliveInterval.*/ClientAliveInterval 300/' "$SSH_CONFIG"
    sed -i 's/^#*ClientAliveCountMax.*/ClientAliveCountMax 2/' "$SSH_CONFIG"

    # Restart SSH service
    if systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null; then
        log "SSH service restarted with hardened configuration"
    else
        warn "Could not restart SSH service"
    fi
}

################################################################################
# fail2ban Installation and Configuration
################################################################################

install_fail2ban() {
    log "Installing and configuring fail2ban..."

    if command -v apt-get &> /dev/null; then
        apt-get install -y fail2ban
    elif command -v yum &> /dev/null; then
        yum install -y fail2ban
    else
        warn "Could not install fail2ban automatically"
        return
    fi

    # Create jail.local configuration
    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
destemail = security@hp-ti.local
sendername = HP_TI Security
action = %(action_mwl)s

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200
EOF

    systemctl enable --now fail2ban
    log "fail2ban configured and enabled"
}

################################################################################
# SELinux/AppArmor Configuration
################################################################################

configure_selinux() {
    log "Configuring SELinux..."

    if command -v getenforce &> /dev/null; then
        if [[ "$(getenforce)" == "Disabled" ]]; then
            warn "SELinux is disabled. Enable it in /etc/selinux/config and reboot"
        else
            log "SELinux is enabled and in $(getenforce) mode"

            if [[ "$ENVIRONMENT" == "--production" ]] && [[ "$(getenforce)" == "Permissive" ]]; then
                warn "SELinux should be in Enforcing mode for production"
            fi
        fi
    elif command -v aa-status &> /dev/null; then
        log "AppArmor detected"
        if systemctl is-active --quiet apparmor; then
            log "AppArmor is active"
        else
            warn "AppArmor is not active"
            systemctl enable --now apparmor || warn "Could not enable AppArmor"
        fi
    else
        warn "Neither SELinux nor AppArmor detected"
    fi
}

################################################################################
# File Permissions
################################################################################

set_file_permissions() {
    log "Setting proper file permissions..."

    # Find HP_TI installation directory
    HP_TI_DIR="/opt/hp_ti"  # Adjust as needed

    if [[ -d "$HP_TI_DIR" ]]; then
        # Set directory ownership
        chown -R hp_ti:hp_ti "$HP_TI_DIR" 2>/dev/null || log "hp_ti user not found, skipping ownership change"

        # Set directory permissions
        find "$HP_TI_DIR" -type d -exec chmod 750 {} \;
        find "$HP_TI_DIR" -type f -exec chmod 640 {} \;

        # Make scripts executable
        find "$HP_TI_DIR" -type f -name "*.sh" -exec chmod 750 {} \;
        find "$HP_TI_DIR" -type f -name "*.py" -exec chmod 750 {} \;

        # Protect sensitive files
        if [[ -f "$HP_TI_DIR/.env" ]]; then
            chmod 600 "$HP_TI_DIR/.env"
            log "Protected .env file"
        fi

        if [[ -d "$HP_TI_DIR/config" ]]; then
            chmod 750 "$HP_TI_DIR/config"
            find "$HP_TI_DIR/config" -type f -exec chmod 640 {} \;
        fi

        log "File permissions set for $HP_TI_DIR"
    else
        warn "HP_TI directory not found at $HP_TI_DIR"
    fi
}

################################################################################
# Docker Security
################################################################################

harden_docker() {
    log "Hardening Docker configuration..."

    if ! command -v docker &> /dev/null; then
        warn "Docker not installed, skipping Docker hardening"
        return
    fi

    # Create or update daemon.json
    DOCKER_DAEMON_JSON="/etc/docker/daemon.json"

    cat > "$DOCKER_DAEMON_JSON" <<EOF
{
  "icc": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "userland-proxy": false,
  "no-new-privileges": true
}
EOF

    systemctl restart docker
    log "Docker daemon configuration updated"

    # Scan images for vulnerabilities (if trivy is installed)
    if command -v trivy &> /dev/null; then
        log "Scanning Docker images with Trivy..."
        docker images --format "{{.Repository}}:{{.Tag}}" | grep -v "<none>" | while read -r image; do
            trivy image --severity HIGH,CRITICAL "$image" | tee -a "$LOG_FILE"
        done
    else
        warn "Trivy not installed. Install with: wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add - && echo 'deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main' | sudo tee -a /etc/apt/sources.list.d/trivy.list && sudo apt-get update && sudo apt-get install trivy"
    fi
}

################################################################################
# Kernel Hardening
################################################################################

harden_kernel() {
    log "Hardening kernel parameters..."

    SYSCTL_CONF="/etc/sysctl.d/99-hp_ti-hardening.conf"

    cat > "$SYSCTL_CONF" <<EOF
# IP Forwarding (disable if not needed)
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0

# SYN cookies protection
net.ipv4.tcp_syncookies = 1

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Ignore send redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Disable source packet routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0

# Log Martians
net.ipv4.conf.all.log_martians = 1

# Ignore ICMP ping requests
net.ipv4.icmp_echo_ignore_all = 0

# Ignore Broadcast Request
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Bad Error Message Protection
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Reverse path filtering
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# TCP/IP stack tuning
net.ipv4.tcp_timestamps = 0
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 5

# IPv6 privacy extensions
net.ipv6.conf.all.use_tempaddr = 2
net.ipv6.conf.default.use_tempaddr = 2

# Kernel hardening
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.yama.ptrace_scope = 1
kernel.kexec_load_disabled = 1

# File system hardening
fs.suid_dumpable = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
EOF

    sysctl -p "$SYSCTL_CONF"
    log "Kernel parameters hardened"
}

################################################################################
# Audit Logging
################################################################################

configure_audit_logging() {
    log "Configuring audit logging..."

    if ! command -v auditd &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            apt-get install -y auditd
        elif command -v yum &> /dev/null; then
            yum install -y audit
        fi
    fi

    if command -v auditd &> /dev/null; then
        systemctl enable --now auditd

        # Add audit rules
        cat >> /etc/audit/rules.d/hp_ti.rules <<EOF
# HP_TI Security Audit Rules

# Monitor file changes
-w /opt/hp_ti/config/ -p wa -k hp_ti_config_changes
-w /etc/hp_ti/ -p wa -k hp_ti_etc_changes

# Monitor authentication
-w /var/log/auth.log -p wa -k authentication

# Monitor network configuration changes
-w /etc/hosts -p wa -k network_modifications
-w /etc/network/ -p wa -k network_modifications

# Monitor Docker
-w /usr/bin/docker -p wa -k docker
-w /var/lib/docker -p wa -k docker

# Monitor user/group changes
-w /etc/group -p wa -k group_modifications
-w /etc/passwd -p wa -k user_modifications
-w /etc/shadow -p wa -k user_modifications
-w /etc/sudoers -p wa -k sudoers_modifications

# Monitor process execution
-a exit,always -F arch=b64 -S execve -k exec
-a exit,always -F arch=b32 -S execve -k exec
EOF

        service auditd restart 2>/dev/null || systemctl restart auditd
        log "Audit logging configured"
    else
        warn "Could not install/configure auditd"
    fi
}

################################################################################
# Disable Unnecessary Services
################################################################################

disable_unnecessary_services() {
    log "Disabling unnecessary services..."

    SERVICES_TO_DISABLE=("avahi-daemon" "cups" "bluetooth" "iscsid" "rpcbind")

    for service in "${SERVICES_TO_DISABLE[@]}"; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            systemctl stop "$service"
            systemctl disable "$service"
            log "Disabled service: $service"
        fi
    done
}

################################################################################
# Security Scan
################################################################################

run_security_scan() {
    log "Running security scans..."

    # Install security tools if not present
    if ! command -v lynis &> /dev/null; then
        warn "Lynis not installed. Install with: apt-get install lynis (Debian/Ubuntu) or yum install lynis (RHEL/CentOS)"
    else
        log "Running Lynis security audit..."
        lynis audit system --quick --quiet | tee -a "$LOG_FILE"
    fi

    # Check for rootkits
    if ! command -v rkhunter &> /dev/null; then
        warn "rkhunter not installed. Install with: apt-get install rkhunter"
    else
        log "Running rkhunter scan..."
        rkhunter --update
        rkhunter --check --skip-keypress | tee -a "$LOG_FILE"
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    check_root

    log "Starting HP_TI security hardening for environment: $ENVIRONMENT"
    log "Logging to: $LOG_FILE"

    update_system
    configure_firewall
    harden_ssh
    install_fail2ban
    configure_selinux
    set_file_permissions
    harden_docker
    harden_kernel
    configure_audit_logging
    disable_unnecessary_services
    run_security_scan

    log "="
    log "Security hardening complete!"
    log "Please review the log file: $LOG_FILE"
    log "="
    warn "IMPORTANT: Verify SSH access before logging out!"
    warn "IMPORTANT: Review firewall rules to ensure they meet your requirements"

    if [[ "$ENVIRONMENT" == "--production" ]]; then
        warn "PRODUCTION: Ensure all checklist items in security_checklist.md are completed"
        warn "PRODUCTION: Test failover and disaster recovery procedures"
        warn "PRODUCTION: Schedule penetration testing"
    fi
}

# Run main function
main "$@"
