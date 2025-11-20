#!/bin/bash
################################################################################
# HP_TI Deployment Script
#
# Automates deployment of HP_TI platform with health checks and rollback support.
#
# Usage: ./deploy.sh [--environment ENV] [--version VERSION]
################################################################################

set -euo pipefail

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
VERSION="${VERSION:-latest}"
DEPLOY_DIR="/opt/hp_ti"
BACKUP_DIR="/opt/hp_ti_backups"
LOG_FILE="/var/log/hp_ti_deploy_$(date +%Y%m%d_%H%M%S).log"

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
        --environment) ENVIRONMENT="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        *) error "Unknown option: $1" ;;
    esac
done

log "Starting deployment for environment: $ENVIRONMENT, version: $VERSION"

# Pre-deployment checks
log "Running pre-deployment checks..."
./health_check.sh --pre-deploy || error "Pre-deployment health check failed"

# Backup current deployment
log "Creating backup..."
BACKUP_NAME="hp_ti_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$DEPLOY_DIR" . || warn "Backup failed"

# Pull latest code/images
log "Pulling latest version..."
cd "$DEPLOY_DIR"
git fetch origin
git checkout "$VERSION" || error "Failed to checkout version $VERSION"

# Update dependencies
log "Updating dependencies..."
docker-compose pull || error "Failed to pull Docker images"

# Run database migrations
log "Running database migrations..."
docker-compose run --rm honeypot python scripts/init_database.py || error "Database migration failed"

# Deploy new version
log "Deploying new version..."
docker-compose up -d || error "Deployment failed"

# Wait for services to start
log "Waiting for services to start..."
sleep 30

# Post-deployment health check
log "Running post-deployment health checks..."
if ! ./health_check.sh --post-deploy; then
    error "Post-deployment health check failed. Rolling back..."
    ./rollback.sh --backup "$BACKUP_NAME"
    error "Deployment failed and rolled back"
fi

log "Deployment successful!"
log "Backup saved to: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
