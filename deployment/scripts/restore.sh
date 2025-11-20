#!/bin/bash
################################################################################
# HP_TI Restore Script
#
# Restores from backup for disaster recovery.
#
# Usage: ./restore.sh --backup TIMESTAMP [--database-only] [--config-only]
################################################################################

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/hp_ti}"
BACKUP_TIMESTAMP=""
RESTORE_TYPE="full"
LOG_FILE="/var/log/hp_ti_restore_$(date +%Y%m%d_%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup) BACKUP_TIMESTAMP="$2"; shift 2 ;;
        --database-only) RESTORE_TYPE="database"; shift ;;
        --config-only) RESTORE_TYPE="config"; shift ;;
        --elasticsearch-only) RESTORE_TYPE="elasticsearch"; shift ;;
        *) error "Unknown option: $1" ;;
    esac
done

[[ -z "$BACKUP_TIMESTAMP" ]] && error "Backup timestamp required: --backup YYYYMMDD_HHMMSS"

log "Starting restore from backup: $BACKUP_TIMESTAMP"
log "Restore type: $RESTORE_TYPE"

################################################################################
# Pre-Restore Checks
################################################################################

pre_restore_checks() {
    log "Running pre-restore checks..."

    # Check if backup exists
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error "Backup directory not found: $BACKUP_DIR"
    fi

    # Check if specific backup exists
    local backup_found=false
    for file in "$BACKUP_DIR"/*/*"${BACKUP_TIMESTAMP}"*; do
        if [[ -f "$file" ]]; then
            backup_found=true
            break
        fi
    done

    if [[ "$backup_found" == "false" ]]; then
        error "No backup found for timestamp: $BACKUP_TIMESTAMP"
    fi

    # Verify checksums
    log "Verifying backup integrity..."
    for checksum_file in "$BACKUP_DIR"/*/*"${BACKUP_TIMESTAMP}"*.sha256; do
        if [[ -f "$checksum_file" ]]; then
            if sha256sum -c "$checksum_file" --status; then
                log "✓ Checksum verified: $(basename "$checksum_file")"
            else
                error "✗ Checksum verification failed: $(basename "$checksum_file")"
            fi
        fi
    done

    log "Pre-restore checks passed"
}

################################################################################
# Database Restore
################################################################################

restore_database() {
    log "Restoring PostgreSQL database..."

    local backup_file="$BACKUP_DIR/database/postgres_${BACKUP_TIMESTAMP}.sql.gz"

    if [[ ! -f "$backup_file" ]]; then
        error "Database backup not found: $backup_file"
    fi

    # Stop application to prevent writes during restore
    log "Stopping application..."
    docker-compose -f /opt/hp_ti/docker-compose.yml stop honeypot || warn "Could not stop honeypot"

    # Drop existing connections
    log "Terminating existing database connections..."
    docker exec hp_ti_postgres psql -U hp_ti_user -c \
        "SELECT pg_terminate_backend(pg_stat_activity.pid)
         FROM pg_stat_activity
         WHERE pg_stat_activity.datname = 'hp_ti_db'
         AND pid <> pg_backend_pid();" \
        || warn "Could not terminate connections"

    # Restore database
    log "Restoring database from: $backup_file"
    zcat "$backup_file" | docker exec -i hp_ti_postgres psql -U hp_ti_user \
        || error "Database restore failed"

    log "Database restored successfully"

    # Restart application
    log "Restarting application..."
    docker-compose -f /opt/hp_ti/docker-compose.yml up -d \
        || warn "Could not restart application"
}

################################################################################
# Configuration Restore
################################################################################

restore_config() {
    log "Restoring configuration files..."

    local config_backup="$BACKUP_DIR/config/config_${BACKUP_TIMESTAMP}.tar.gz"

    if [[ ! -f "$config_backup" ]]; then
        error "Configuration backup not found: $config_backup"
    fi

    # Backup current config before restore
    local current_config_backup="/tmp/hp_ti_config_pre_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$current_config_backup" -C /opt/hp_ti config/ .env docker-compose.yml 2>/dev/null \
        || warn "Could not backup current config"

    log "Current config backed up to: $current_config_backup"

    # Restore config
    log "Restoring configuration from: $config_backup"
    tar -xzf "$config_backup" -C /opt/hp_ti/ \
        || error "Configuration restore failed"

    log "Configuration restored successfully"

    # Restart services to apply new config
    log "Restarting services..."
    docker-compose -f /opt/hp_ti/docker-compose.yml restart \
        || warn "Could not restart services"
}

################################################################################
# Elasticsearch Restore
################################################################################

restore_elasticsearch() {
    log "Restoring Elasticsearch indices..."

    local snapshot_name="snapshot_${BACKUP_TIMESTAMP}"
    local es_backup="$BACKUP_DIR/elasticsearch/${snapshot_name}.tar.gz"

    if [[ ! -f "$es_backup" ]]; then
        warn "Elasticsearch backup not found: $es_backup"
        return
    fi

    # Copy backup to Elasticsearch container
    docker cp "$es_backup" "hp_ti_elasticsearch:/usr/share/elasticsearch/backups/" \
        || error "Could not copy Elasticsearch backup"

    # Extract backup
    docker exec hp_ti_elasticsearch \
        tar -xzf "/usr/share/elasticsearch/backups/${snapshot_name}.tar.gz" \
        -C /usr/share/elasticsearch/backups/ \
        || error "Could not extract Elasticsearch backup"

    # Close indices before restore
    log "Closing Elasticsearch indices..."
    curl -X POST "localhost:9200/hp_ti_*/_close" \
        || warn "Could not close indices"

    # Restore snapshot
    log "Restoring Elasticsearch snapshot: $snapshot_name"
    curl -X POST "localhost:9200/_snapshot/hp_ti_backups/${snapshot_name}/_restore?wait_for_completion=true" \
        -H 'Content-Type: application/json' \
        -d'{
            "indices": "hp_ti_*",
            "ignore_unavailable": true,
            "include_global_state": false
        }' || error "Elasticsearch restore failed"

    # Reopen indices
    log "Reopening Elasticsearch indices..."
    curl -X POST "localhost:9200/hp_ti_*/_open" \
        || warn "Could not reopen indices"

    log "Elasticsearch restored successfully"
}

################################################################################
# Log Restore
################################################################################

restore_logs() {
    log "Restoring application logs..."

    local log_backup="$BACKUP_DIR/logs/logs_${BACKUP_TIMESTAMP}.tar.gz"

    if [[ ! -f "$log_backup" ]]; then
        warn "Log backup not found: $log_backup"
        return
    fi

    # Backup current logs
    if [[ -d /opt/hp_ti/logs ]]; then
        mv /opt/hp_ti/logs "/opt/hp_ti/logs.old.$(date +%Y%m%d_%H%M%S)"
    fi

    # Restore logs
    tar -xzf "$log_backup" -C /opt/hp_ti/ \
        || warn "Log restore failed"

    log "Logs restored successfully"
}

################################################################################
# Post-Restore Verification
################################################################################

post_restore_verification() {
    log "Running post-restore verification..."

    # Wait for services to start
    sleep 15

    # Check database connection
    if docker exec hp_ti_postgres pg_isready -U hp_ti_user &> /dev/null; then
        log "✓ Database is responsive"
    else
        error "✗ Database is not responsive"
    fi

    # Check Elasticsearch
    if curl -s "localhost:9200/_cluster/health" | grep -q '"status":"green\|yellow"'; then
        log "✓ Elasticsearch is healthy"
    else
        warn "✗ Elasticsearch may have issues"
    fi

    # Run health checks
    if /opt/hp_ti/deployment/scripts/health_check.sh; then
        log "✓ All health checks passed"
    else
        warn "✗ Some health checks failed"
    fi

    log "Post-restore verification complete"
}

################################################################################
# Main Execution
################################################################################

main() {
    log "HP_TI Disaster Recovery Restore"
    log "================================"
    log "Backup timestamp: $BACKUP_TIMESTAMP"
    log "Restore type: $RESTORE_TYPE"
    log "Backup directory: $BACKUP_DIR"
    log ""

    warn "⚠️  WARNING: This will overwrite current data!"
    warn "⚠️  Ensure you have a backup of the current state!"

    if [[ "${SKIP_CONFIRMATION:-}" != "yes" ]]; then
        read -p "Continue with restore? (type 'yes' to proceed): " -r
        if [[ ! $REPLY == "yes" ]]; then
            error "Restore cancelled by user"
        fi
    fi

    # Run pre-restore checks
    pre_restore_checks

    # Perform restore based on type
    case $RESTORE_TYPE in
        full)
            restore_database
            restore_config
            restore_elasticsearch
            restore_logs
            ;;
        database)
            restore_database
            ;;
        config)
            restore_config
            ;;
        elasticsearch)
            restore_elasticsearch
            ;;
        *)
            error "Unknown restore type: $RESTORE_TYPE"
            ;;
    esac

    # Post-restore verification
    post_restore_verification

    log ""
    log "================================"
    log "Restore completed successfully!"
    log "================================"
    log "Restored from: $BACKUP_TIMESTAMP"
    log "Restore type: $RESTORE_TYPE"
    log "Log file: $LOG_FILE"
    log ""
    warn "Next steps:"
    log "1. Verify application functionality"
    log "2. Check logs for any errors"
    log "3. Monitor system for 24 hours"
    log "4. Update documentation with restore details"
}

# Execute main function
main
