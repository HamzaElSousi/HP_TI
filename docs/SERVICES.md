# HP_TI Honeypot Services Documentation

## Overview

HP_TI implements multiple low-interaction honeypot services to attract and log malicious activity across common network protocols. All services are designed with security-first principles, ensuring they cannot be used as pivot points for lateral movement.

## Table of Contents

- [Service Manager](#service-manager)
- [SSH Honeypot](#ssh-honeypot)
- [HTTP/HTTPS Honeypot](#httphttps-honeypot)
- [Telnet Honeypot](#telnet-honeypot)
- [FTP Honeypot](#ftp-honeypot)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Security Considerations](#security-considerations)

---

## Service Manager

The Service Manager orchestrates all honeypot services with unified start/stop, health monitoring, and graceful shutdown capabilities.

### Features

- **Multi-service orchestration**: Manages SSH, HTTP, Telnet, and FTP honeypots
- **Health monitoring**: Automatic restart of failed services
- **Graceful shutdown**: Proper cleanup on SIGTERM/SIGINT
- **Status reporting**: Real-time service status and statistics
- **Independent service control**: Start, stop, or restart individual services

### Usage

```bash
# Start all enabled services
python main.py

# Show service status
python main.py --status

# Run health check
python main.py --health

# Specify custom config and log directory
python main.py --config config/custom.yaml --log-dir /var/log/honeypot
```

### API

```python
from honeypot.service_manager import ServiceManager

# Create service manager
manager = ServiceManager(config_path=Path("config/config.yaml"))

# Start all services
await manager.start_all()

# Get service status
status = manager.get_status()

# Get health check
health = await manager.health_check()

# Restart specific service
await manager.restart_service("ssh")

# Stop all services
await manager.stop_all()
```

---

## SSH Honeypot

Low-interaction SSH honeypot that simulates shell access and captures authentication attempts and commands.

### Features

- **Authentication capture**: Logs all username/password attempts
- **Command capture**: Records all commands entered by attackers
- **Fake shell environment**: Simulates realistic shell responses
- **Session tracking**: Unique session IDs for correlation
- **Connection limits**: Configurable max connections per IP

### Configuration

```yaml
ssh:
  enabled: true
  host: 0.0.0.0
  port: 2222
  banner: "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1"
  session_timeout: 300  # seconds
  max_connections_per_ip: 5
```

### Captured Data

- **Authentication attempts**: Username, password, timestamp
- **Commands**: All commands entered during the session
- **Session metadata**: Duration, source IP, connection time
- **Fake responses**: Simulated output for common commands

### Common Attack Patterns Detected

- Brute force authentication attempts
- Credential stuffing
- Automated scanning (Mirai, etc.)
- Common admin password attempts
- Reconnaissance commands

---

## HTTP/HTTPS Honeypot

Web honeypot that simulates admin panels, vulnerable applications, and captures web-based attacks.

### Features

- **Admin panel simulation**: Fake login pages for /admin, /wp-admin, /phpmyadmin
- **Attack detection**: SQL injection, XSS, path traversal, command injection
- **Request logging**: Full HTTP request capture (headers, params, body)
- **Session tracking**: Correlates multiple requests from same attacker
- **Attack classification**: Automatically identifies attack types

### Configuration

```yaml
http:
  enabled: true
  host: 0.0.0.0
  port: 8080
  https_port: 8443
```

### Simulated Endpoints

- `/admin` - Generic admin panel
- `/wp-admin` - WordPress admin
- `/phpmyadmin` - PHPMyAdmin
- `/administrator` - Joomla admin
- `/cpanel` - cPanel login
- `/shell.php` - Webshell detection
- `/.env`, `/.git/config` - Config file exposure

### Attack Types Detected

1. **SQL Injection**
   - Single quote exploits
   - UNION SELECT statements
   - Boolean-based blind injection
   - OR 1=1 patterns

2. **XSS (Cross-Site Scripting)**
   - `<script>` tag injection
   - JavaScript event handlers
   - HTML entity encoding attempts

3. **Path Traversal**
   - `../` directory traversal
   - `/etc/passwd` access attempts
   - Windows-style traversal (`..\\`)

4. **Command Injection**
   - Shell command separators (`;`, `|`, `&&`)
   - Backtick execution
   - Process substitution

5. **Webshell Access**
   - Common webshell filenames
   - PHP/ASP webshell patterns

6. **Config File Exposure**
   - `.env` file access
   - `.git` directory exposure
   - Configuration backups

### Captured Data

- **HTTP requests**: Method, path, headers, query parameters
- **POST data**: Form data and JSON payloads
- **Attack indicators**: Detected attack type and patterns
- **Session data**: IP, user-agent, cookies, timestamps

---

## Telnet Honeypot

Simulates IoT devices and legacy systems vulnerable to telnet-based attacks.

### Features

- **Device profiles**: Router, IP Camera, DVR simulations
- **Realistic banners**: Device-specific login prompts
- **Command capture**: All telnet commands logged
- **Authentication rejection**: Always rejects login attempts
- **IoT attack detection**: Mirai, botnet patterns

### Configuration

```yaml
telnet:
  enabled: true
  host: 0.0.0.0
  port: 2323
```

### Device Profiles

#### 1. Router Profile
```
Welcome to Generic Router
Login: _
```

- Common commands: `show version`, `show ip`, `help`
- Simulates Cisco/generic router interface

#### 2. IP Camera Profile
```
IP Camera System v2.1
login: _
```

- Common commands: `snapshot`, `config`, `reboot`
- Simulates CCTV/security camera systems

#### 3. DVR Profile
```
DVR System Console
Username: _
```

- Common commands: `status`, `record`, `playback`
- Simulates digital video recorder systems

### Common IoT Attack Patterns

- **Default credentials**: admin/admin, root/root, admin/12345
- **Mirai botnet**: Specific credential lists
- **Command execution**: `cat /proc/cpuinfo`, `wget malware`
- **Persistence**: Creating backdoor users

### Captured Data

- **Login attempts**: Username, password combinations
- **Commands**: All commands attempted
- **Device profile**: Which simulated device was targeted
- **Session metadata**: Connection details, duration

---

## FTP Honeypot

FTP server honeypot that captures file transfer attempts and authentication.

### Features

- **FTP protocol simulation**: Proper FTP response codes
- **Authentication capture**: USER/PASS command logging
- **File operation logging**: RETR, STOR attempts captured
- **Fake directory structure**: Simulated file system
- **FTP-specific attacks**: Bounce attacks, anonymous login attempts

### Configuration

```yaml
ftp:
  enabled: true
  host: 0.0.0.0
  port: 2121
```

### Supported FTP Commands

#### Authentication
- `USER` - Username submission (always prompts for password)
- `PASS` - Password submission (always rejects)

#### Session Management
- `SYST` - System type (returns "UNIX Type: L8")
- `QUIT` - Close connection
- `TYPE` - Set transfer type (ASCII/Binary)

#### Directory Operations
- `PWD` - Print working directory
- `CWD` - Change directory (fake navigation)
- `LIST` - List files (not implemented)

#### File Operations
- `RETR` - Download file (logs attempt, returns error)
- `STOR` - Upload file (logs attempt, returns error)

#### Data Connection
- `PORT` - Active mode (not implemented)
- `PASV` - Passive mode (not implemented)

### Fake File System

**Directories:**
- `/uploads`
- `/downloads`
- `/public`
- `/private`
- `/backups`

**Files:**
- `README.txt`
- `index.html`
- `config.ini`
- `data.csv`
- `backup.zip`
- `log.txt`

### Attack Patterns Detected

- **Anonymous FTP**: Anonymous login attempts
- **Brute force**: Password guessing
- **File exfiltration**: Download attempts of sensitive files
- **Malware upload**: STOR commands for executables
- **FTP bounce attacks**: PORT command manipulation

### Captured Data

- **Authentication**: All USER/PASS combinations
- **File operations**: Attempted downloads/uploads
- **Directory traversal**: CWD path attempts
- **Session metadata**: IP, timestamps, command sequence

---

## Configuration

### Global Configuration File

Create `config/config.yaml` from the example:

```bash
cp config/config.example.yaml config/config.yaml
```

### Environment Variables

All services support configuration via environment variables:

```bash
# SSH Honeypot
export HONEYPOT_SSH_ENABLED=true
export HONEYPOT_SSH_PORT=2222
export HONEYPOT_SSH_HOST=0.0.0.0

# HTTP Honeypot
export HONEYPOT_HTTP_ENABLED=true
export HONEYPOT_HTTP_PORT=8080
export HONEYPOT_HTTP_HTTPS_PORT=8443

# Telnet Honeypot
export HONEYPOT_TELNET_ENABLED=true
export HONEYPOT_TELNET_PORT=2323

# FTP Honeypot
export HONEYPOT_FTP_ENABLED=true
export HONEYPOT_FTP_PORT=2121
```

### Selective Service Enablement

Enable only specific services:

```yaml
ssh:
  enabled: true
http:
  enabled: true
telnet:
  enabled: false  # Disabled
ftp:
  enabled: false  # Disabled
```

---

## Deployment

### Docker Deployment

#### Start All Services

```bash
cd deployment/docker
docker-compose up -d
```

#### Start with Visualization Tools

```bash
docker-compose --profile visualization up -d
```

This includes:
- Kibana (port 5601)
- Grafana (port 3000)
- Prometheus (port 9090)

#### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f honeypot
```

### Standalone Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default config
python main.py

# Run with custom config
python main.py --config /path/to/config.yaml
```

### Production Deployment

For production deployments:

1. **Change default ports** if running as non-root:
   ```yaml
   ssh:
     port: 2222  # Use non-privileged ports
   http:
     port: 8080
   ```

2. **Use reverse proxy** to forward privileged ports (22, 80, 443):
   ```nginx
   # nginx example
   server {
     listen 22;
     proxy_pass localhost:2222;
   }
   ```

3. **Enable logging to persistent storage**:
   ```yaml
   logging:
     dir: /var/log/hp_ti
   ```

4. **Configure database persistence**:
   - Use external PostgreSQL/Elasticsearch instances
   - Set up regular backups

---

## Monitoring

### Service Status

```bash
# Check service status
python main.py --status

# Output:
# SSH:
#   name: ssh
#   running: True
#   start_time: 2025-01-15T10:30:00.000000
#   uptime_seconds: 3600.5
```

### Health Checks

```bash
# Run health check
python main.py --health

# Output:
# Overall Status: HEALTHY
# Services:
#   ✓ ssh: healthy
#   ✓ http: healthy
#   ✓ telnet: healthy
#   ✓ ftp: healthy
```

### Log Monitoring

All services log to structured JSON format:

```json
{
  "timestamp": "2025-01-15T10:30:15.123Z",
  "level": "INFO",
  "component": "ssh_honeypot",
  "event_type": "auth_attempt",
  "source_ip": "192.168.1.100",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "admin",
  "password": "password123",
  "success": false
}
```

### Metrics

Key metrics to monitor:

- **Connection rate**: Connections per minute/hour
- **Authentication attempts**: Failed login rates
- **Attack patterns**: Distribution of attack types
- **Top attackers**: Most active source IPs
- **Geographic distribution**: Attack origins

---

## Security Considerations

### Isolation

- **Network isolation**: Run honeypots in isolated network segments
- **Container isolation**: Use Docker with limited capabilities
- **No outbound access**: Prevent honeypots from initiating outbound connections

### Data Sanitization

- **SQL injection**: All captured data is sanitized before database insertion
- **Command injection**: Shell commands are never executed
- **XSS prevention**: Logs are properly escaped in web interfaces

### Access Control

- **Authentication always fails**: No valid credentials exist
- **Read-only filesystems**: No file uploads are actually saved
- **No code execution**: Commands are logged but never executed

### Monitoring & Alerting

- **Failed service detection**: Auto-restart crashed services
- **Unusual activity**: Alert on abnormal connection rates
- **Data exfiltration**: Monitor for large data transfers

### Legal Considerations

- **Terms of Service**: Display banner warning unauthorized access
- **Data retention**: Comply with data protection regulations
- **Responsible disclosure**: Report coordinated attacks to relevant authorities

---

## Troubleshooting

### Service Won't Start

**Port already in use:**
```bash
# Check what's using the port
lsof -i :2222

# Kill the process or change honeypot port
```

**Permission denied:**
```bash
# Use non-privileged ports (>1024) or run with sudo
# Recommended: Use non-privileged ports + iptables redirect
```

### No Logs Generated

```bash
# Check log directory permissions
ls -la logs/

# Verify logging configuration
python -c "from honeypot.config.config_loader import get_config; print(get_config().logging.dir)"
```

### Database Connection Errors

```bash
# Test database connectivity
docker-compose exec postgres psql -U hp_ti_user -d hp_ti_db

# Check DATABASE_URL environment variable
echo $DATABASE_URL
```

---

## Development

### Adding Custom Honeypot Services

1. Create service class in `honeypot/services/`
2. Implement `start()` and `stop()` methods
3. Add configuration to `config_loader.py`
4. Register in `ServiceManager._init_services()`
5. Add tests in `tests/unit/`

### Testing Services

```bash
# Run all tests
pytest tests/

# Test specific service
pytest tests/unit/test_http_honeypot.py -v

# Run with coverage
pytest --cov=honeypot tests/
```

---

## References

- [HP_TI Architecture](architecture/ARCHITECTURE.md)
- [Data Pipeline Documentation](DATA_PIPELINE.md)
- [Threat Intelligence](THREAT_INTELLIGENCE.md)
- [Implementation Plan](../IMPLEMENTATION_PLAN.md)

---

**Last Updated**: 2025-01-15
**Version**: Phase 4 - Multi-Protocol Honeypots
