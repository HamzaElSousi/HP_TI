#!/bin/bash
################################################################################
# HP_TI Backup Script
#
# Automates backup of databases, configurations, and logs.
#
# Usage: ./backup.sh [--full|--incremental] [--verify]
################################################################################

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/hp_ti}"
BACKUP_TYPE="${1:---full}"
VERIFY="${2:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/hp_ti_backup_${TIMESTAMP}.log"
RETENTION_DAYS=30

# S3 Configuration (optional)
S3_BUCKET="${S3_BUCKET:-}"
S3_REGION="${S3_REGION:-us-east-1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; exit 1; }

# Create backup directories
mkdir -p "$BACKUP_DIR"/{database,config,logs,elasticsearch}

log "Starting backup: $BACKUP_TYPE at $TIMESTAMP"

################################################################################
# Database Backup
################################################################################

backup_database() {
    log "Backing up PostgreSQL database..."

    BACKUP_FILE="$BACKUP_DIR/database/postgres_${TIMESTAMP}.sql.gz"

    docker exec hp_ti_postgres pg_dumpall -U hp_ti_user | gzip > "$BACKUP_FILE" \
        || error "Database backup failed"

    log "Database backup saved to: $BACKUP_FILE"

    # Calculate checksum
    sha256sum "$BACKUP_FILE" > "$BACKUP_FILE.sha256"

    log "Database backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
}

################################################################################
# Configuration Backup
################################################################################

backup_config() {
    log "Backing up configuration files..."

    CONFIG_BACKUP="$BACKUP_DIR/config/config_${TIMESTAMP}.tar.gz"

    tar -czf "$CONFIG_BACKUP" \
        -C /opt/hp_ti \
        config/ \
        .env \
        docker-compose.yml \
        || warn "Some config files may be missing"

    log "Configuration backup saved to: $CONFIG_BACKUP"

    # Calculate checksum
    sha256sum "$CONFIG_BACKUP" > "$CONFIG_BACKUP.sha256"
}

################################################################################
# Elasticsearch Backup
################################################################################

backup_elasticsearch() {
    log "Backing up Elasticsearch indices..."

    # Create snapshot repository if not exists
    curl -X PUT "localhost:9200/_snapshot/hp_ti_backups" \
        -H 'Content-Type: application/json' \
        -d"{
            \"type\": \"fs\",
            \"settings\": {
                \"location\": \"/usr/share/elasticsearch/backups\"
            }
        }" 2>/dev/null || warn "Snapshot repository may already exist"

    # Create snapshot
    SNAPSHOT_NAME="snapshot_${TIMESTAMP}"
    curl -X PUT "localhost:9200/_snapshot/hp_ti_backups/${SNAPSHOT_NAME}?wait_for_completion=true" \
        -H 'Content-Type: application/json' \
        -d'{
            "indices": "hp_ti_*",
            "ignore_unavailable": true,
            "include_global_state": false
        }' 2>/dev/null || error "Elasticsearch snapshot failed"

    log "Elasticsearch snapshot created: $SNAPSHOT_NAME"

    # Export snapshot to backup directory
    docker exec hp_ti_elasticsearch \
        tar -czf "/usr/share/elasticsearch/backups/${SNAPSHOT_NAME}.tar.gz" \
        -C /usr/share/elasticsearch/backups . \
        || warn "Elasticsearch export failed"

    docker cp "hp_ti_elasticsearch:/usr/share/elasticsearch/backups/${SNAPSHOT_NAME}.tar.gz" \
        "$BACKUP_DIR/elasticsearch/" \
        || warn "Could not copy Elasticsearch backup"
}

################################################################################
# Log Backup
################################################################################

backup_logs() {
    log "Backing up application logs..."

    LOG_BACKUP="$BACKUP_DIR/logs/logs_${TIMESTAMP}.tar.gz"

    if [[ -d /opt/hp_ti/logs ]]; then
        tar -czf "$LOG_BACKUP" -C /opt/hp_ti logs/ \
            || warn "Log backup incomplete"

        log "Log backup saved to: $LOG_BACKUP"
    else
        warn "Log directory not found, skipping log backup"
    fi
}

################################################################################
# Verification
################################################################################

verify_backup() {
    log "Verifying backup integrity..."

    VERIFICATION_FAILED=0

    # Verify checksums
    for checksum_file in "$BACKUP_DIR"/*/*.sha256; do
        if [[ -f "$checksum_file" ]]; then
            if sha256sum -c "$checksum_file" --status; then
                log "✓ Verified: $(basename "$checksum_file")"
            else
                error "✗ Verification failed: $(basename "$checksum_file")"
                ((VERIFICATION_FAILED++))
            fi
        fi
    done

    # Test database restore (dry run)
    log "Testing database backup..."
    if zcat "$BACKUP_DIR/database/postgres_${TIMESTAMP}.sql.gz" | head -n 100 > /dev/null; then
        log "✓ Database backup is readable"
    else
        error "✗ Database backup is corrupted"
        ((VERIFICATION_FAILED++))
    fi

    if [[ $VERIFICATION_FAILED -eq 0 ]]; then
        log "All backup verifications passed"
    else
        error "Backup verification failed with $VERIFICATION_FAILED errors"
    fi
}

################################################################################
# Cloud Upload
################################################################################

upload_to_s3() {
    if [[ -z "$S3_BUCKET" ]]; then
        log "S3 upload not configured, skipping"
        return
    fi

    log "Uploading backups to S3: s3://$S3_BUCKET/hp_ti/"

    if command -v aws &> /dev/null; then
        aws s3 sync "$BACKUP_DIR" "s3://$S3_BUCKET/hp_ti/" \
            --region "$S3_REGION" \
            --storage-class STANDARD_IA \
            || warn "S3 upload failed"

        log "Backups uploaded to S3"
    else
        warn "AWS CLI not installed, skipping S3 upload"
    fi
}

################################################################################
# Cleanup Old Backups
################################################################################

cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."

    find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete

    DELETED_COUNT=$(find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)
    log "Deleted $DELETED_COUNT old backup files"
}

################################################################################
# Main Execution
################################################################################

main() {
    log "Backup configuration:"
    log "  Type: $BACKUP_TYPE"
    log "  Directory: $BACKUP_DIR"
    log "  Timestamp: $TIMESTAMP"
    log "  Retention: $RETENTION_DAYS days"

    # Perform backups
    backup_database
    backup_config
    backup_elasticsearch
    backup_logs

    # Verify if requested
    if [[ "$VERIFY" == "--verify" ]]; then
        verify_backup
    fi

    # Upload to cloud
    upload_to_s3

    # Cleanup old backups
    cleanup_old_backups

    # Summary
    log "Backup completed successfully!"
    log "Backup location: $BACKUP_DIR"
    log "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
    log "Log file: $LOG_FILE"

    # Create backup manifest
    cat > "$BACKUP_DIR/manifest_${TIMESTAMP}.txt" <<EOF
HP_TI Backup Manifest
=====================
Timestamp: $TIMESTAMP
Type: $BACKUP_TYPE
Hostname: $(hostname)

Files:
$(find "$BACKUP_DIR" -type f -name "*${TIMESTAMP}*" -exec ls -lh {} \;)

Total Size: $(du -sh "$BACKUP_DIR" | cut -f1)
EOF

    log "Backup manifest: $BACKUP_DIR/manifest_${TIMESTAMP}.txt"
}

# Execute main function
main
