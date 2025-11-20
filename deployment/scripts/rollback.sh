#!/bin/bash
################################################################################
# HP_TI Rollback Script
#
# Rolls back to previous deployment version.
#
# Usage: ./rollback.sh [--backup BACKUP_NAME]
################################################################################

set -euo pipefail

BACKUP_DIR="/opt/hp_ti_backups"
DEPLOY_DIR="/opt/hp_ti"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Parse arguments
BACKUP_NAME=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup) BACKUP_NAME="$2"; shift 2 ;;
        *) error "Unknown option: $1" ;;
    esac
done

# If no backup specified, use the latest
if [[ -z "$BACKUP_NAME" ]]; then
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -1)
    if [[ -z "$LATEST_BACKUP" ]]; then
        error "No backups found in $BACKUP_DIR"
    fi
    BACKUP_NAME=$(basename "$LATEST_BACKUP")
    warn "No backup specified, using latest: $BACKUP_NAME"
fi

BACKUP_FILE="$BACKUP_DIR/$BACKUP_NAME"
[[ "$BACKUP_FILE" != *.tar.gz ]] && BACKUP_FILE="$BACKUP_FILE.tar.gz"

[[ ! -f "$BACKUP_FILE" ]] && error "Backup file not found: $BACKUP_FILE"

log "Rolling back to: $BACKUP_FILE"

# Stop current services
log "Stopping current services..."
cd "$DEPLOY_DIR"
docker-compose down || warn "Failed to stop services gracefully"

# Restore backup
log "Restoring backup..."
rm -rf "$DEPLOY_DIR"/*
tar -xzf "$BACKUP_FILE" -C "$DEPLOY_DIR" || error "Failed to restore backup"

# Start services
log "Starting services..."
cd "$DEPLOY_DIR"
docker-compose up -d || error "Failed to start services"

# Wait and health check
log "Waiting for services..."
sleep 30

if ./deployment/scripts/health_check.sh; then
    log "Rollback successful!"
else
    error "Rollback completed but health checks failed!"
fi
