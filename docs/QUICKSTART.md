# HP_TI Quick Start Guide

This guide will help you get the HP_TI honeypot system up and running quickly.

## Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (for containerized deployment)
- Git

## Option 1: Docker Deployment (Recommended for Testing)

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/HamzaElSousi/HP_TI.git
cd HP_TI

# Create environment file
cp .env.example .env
# Edit .env if needed (defaults work for testing)

# Start all services
cd deployment/docker
docker-compose up -d

# View logs
docker-compose logs -f honeypot

# Test the SSH honeypot
ssh root@localhost -p 2222
# Try password: admin123 (will fail, but be logged)
```

To stop the services:

```bash
docker-compose down
```

To include visualization tools (Grafana, Kibana):

```bash
docker-compose --profile visualization up -d
```

## Option 2: Local Development

For development and customization:

```bash
# Clone the repository
git clone https://github.com/HamzaElSousi/HP_TI.git
cd HP_TI

# Run setup script
./scripts/setup_dev.sh

# Activate virtual environment
source venv/bin/activate

# Start the honeypot
python main.py
```

In another terminal, test the SSH honeypot:

```bash
# Try to connect (will fail to authenticate)
ssh root@localhost -p 2222

# Try some credentials (all will fail but be logged)
# Username: admin, Password: password123
```

## Viewing Logs

### JSON Logs

Logs are stored in the `logs/honeypots/` directory:

```bash
# View SSH honeypot logs
tail -f logs/honeypots/ssh_honeypot.log

# Pretty-print JSON logs
tail -f logs/honeypots/ssh_honeypot.log | jq '.'
```

### Console Logs

When running locally (not in Docker), logs also appear in the console with color coding.

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config_loader.py

# Run with coverage report
pytest --cov=honeypot --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Connecting to Services

When running the full Docker stack:

- **SSH Honeypot**: `ssh root@localhost -p 2222`
- **Kibana** (if enabled): http://localhost:5601
- **Grafana** (if enabled): http://localhost:3000 (admin/admin)
- **Prometheus** (if enabled): http://localhost:9090

## Configuration

### Environment Variables

Edit `.env` to configure:

- Honeypot ports and settings
- Database connections
- Log levels and formats
- Threat intelligence API keys

### YAML Configuration

Edit `config/honeypot_config.yaml` for more detailed configuration.

Environment variables override YAML settings.

## What's Being Logged?

The SSH honeypot logs:

1. **Connection Attempts**:
   - Source IP and port
   - Timestamp
   - Session ID

2. **Authentication Attempts**:
   - Username and password combinations
   - Public key attempts
   - Authentication method

3. **Commands**:
   - All commands typed by attackers
   - Fake responses provided
   - Command timestamps

4. **Session Info**:
   - Session duration
   - Total commands executed
   - Connection lifecycle

## Example Attack Simulation

Try these commands to generate log entries:

```bash
# Connect to honeypot
ssh root@localhost -p 2222

# When prompted for password, try:
# - admin
# - password123
# - root

# Connection will fail, but all attempts are logged
```

View the logged attack:

```bash
# View latest logs
tail -10 logs/honeypots/ssh_honeypot.log | jq '.'
```

## Troubleshooting

### Port Already in Use

If port 2222 is already in use:

```bash
# Check what's using the port
lsof -i :2222

# Change the port in .env
HONEYPOT_SSH_PORT=2223
```

### Permission Denied

If you get permission errors:

```bash
# Make sure log directory is writable
mkdir -p logs/honeypots
chmod 755 logs/honeypots

# If using Docker, check container permissions
docker-compose logs honeypot
```

### Docker Issues

```bash
# Rebuild containers
docker-compose build --no-cache

# Reset everything
docker-compose down -v
docker-compose up -d
```

## Next Steps

1. **Review Logs**: Check `logs/honeypots/ssh_honeypot.log` for captured data
2. **Customize Responses**: Edit `honeypot/services/ssh_honeypot.py` to add more fake commands
3. **Add More Honeypots**: Enable HTTP, Telnet, or FTP in configuration
4. **Set Up Threat Intel**: Add API keys for AbuseIPDB, VirusTotal, etc.
5. **Enable Visualization**: Start Grafana/Kibana to visualize attacks

## Security Warning

⚠️ **Important**:

- This is a honeypot system designed to attract attackers
- Deploy in an isolated environment
- Do not expose directly to the internet without proper network segmentation
- Review captured data regularly
- Be aware of legal implications in your jurisdiction

## Getting Help

- Check [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines
- Review [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for architecture details
- See [CLAUDE.md](../CLAUDE.md) for AI assistant guidance
- Open an issue on GitHub for bugs or questions

## What's Next?

See the [Implementation Plan](../IMPLEMENTATION_PLAN.md) for upcoming features:

- Phase 2: Data Pipeline & Storage
- Phase 3: Threat Intelligence Enrichment
- Phase 4: Additional Honeypot Services
- Phase 5: Visualization & Alerting
- Phase 6: Production Hardening

Happy honeypotting! 🍯
