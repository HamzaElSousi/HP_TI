# CLAUDE.md - AI Assistant Guide for HP_TI Project

## Project Overview

**HP_TI (Honeypot & Threat Intelligence)** is a security research project implementing a low-interaction honeypot system with an automated threat intelligence pipeline. The project focuses on:

- **Deception Technology**: Attracting and logging malicious network activity
- **Threat Intelligence**: Processing, enriching, and analyzing captured data
- **Real-time Visualization**: Providing actionable insights into attacker TTPs (Tactics, Techniques, and Procedures)
- **SOAR-like Automation**: Security Orchestration, Automation, and Response processes

## Repository Structure

This is a new project. The expected structure will include:

```
HP_TI/
├── honeypot/              # Honeypot implementation
│   ├── services/          # Individual honeypot services (SSH, HTTP, etc.)
│   ├── logging/           # Log collection and formatting
│   └── config/            # Honeypot configuration files
├── threat_intel/          # Threat intelligence processing
│   ├── enrichment/        # IP/domain enrichment (WHOIS, GeoIP, etc.)
│   ├── parsers/           # Log parsers and data extractors
│   └── correlators/       # Event correlation and pattern detection
├── pipeline/              # Automation and data pipeline
│   ├── ingestion/         # Data ingestion from honeypots
│   ├── processing/        # Data transformation and analysis
│   └── storage/           # Database/storage integrations
├── visualization/         # Dashboards and reporting
│   ├── dashboards/        # Visualization configs (Grafana/Kibana)
│   └── reports/           # Automated report generation
├── deployment/            # Infrastructure and deployment
│   ├── docker/            # Docker configurations
│   ├── kubernetes/        # K8s manifests (if applicable)
│   └── scripts/           # Deployment automation scripts
├── tests/                 # Test suites
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── security/          # Security-specific tests
├── docs/                  # Documentation
│   ├── architecture/      # System architecture docs
│   ├── api/               # API documentation
│   └── playbooks/         # Security playbooks and procedures
├── config/                # Global configuration
├── scripts/               # Utility scripts
└── data/                  # Sample data and test datasets
```

## Development Guidelines for AI Assistants

### 1. Security-First Mindset

**CRITICAL**: This is a security research project dealing with malicious traffic and attacker data.

- **Never introduce vulnerabilities**: Be extra vigilant about security issues
  - SQL injection prevention
  - Command injection prevention
  - XSS/CSRF protection in any web interfaces
  - Proper input validation and sanitization
  - Secure credential management (use environment variables, secrets management)

- **Isolation and sandboxing**: Honeypot components should be properly isolated
  - Use containers/VMs for honeypot services
  - Implement network segmentation
  - Ensure honeypots cannot be used as pivot points

- **Data sanitization**: All attacker data must be sanitized before processing
  - Escape shell commands and scripts from logs
  - Validate IP addresses and domains
  - Be cautious with file uploads or binary data

### 2. Code Quality Standards

**Language Preferences**:
- **Python**: Primary language for honeypot logic, data processing, and automation
- **Go**: For high-performance components or network services
- **Shell scripts**: For deployment and operational tasks
- **JavaScript/TypeScript**: For web dashboards and visualizations

**Code Style**:
- Follow PEP 8 for Python code
- Use type hints in Python (3.8+)
- Document all functions with docstrings
- Include inline comments for complex security logic
- Use meaningful variable names (no single letters except in loops)

**Error Handling**:
- Comprehensive exception handling
- Structured logging (use `logging` module in Python)
- Never expose sensitive information in error messages
- Log all errors with context for debugging

### 3. Logging and Monitoring

**Logging Levels**:
- `DEBUG`: Detailed diagnostic information
- `INFO`: Normal operations and important events
- `WARNING`: Unexpected behavior that doesn't prevent operation
- `ERROR`: Errors that prevent specific operations
- `CRITICAL`: System-wide failures

**Log Format**:
```json
{
  "timestamp": "ISO8601",
  "level": "INFO|WARNING|ERROR",
  "component": "honeypot|pipeline|enrichment",
  "event_type": "connection_attempt|attack_detected|data_processed",
  "source_ip": "x.x.x.x",
  "details": {},
  "metadata": {}
}
```

**What to Log**:
- All incoming connections to honeypots
- Attack attempts and payloads
- Data processing pipeline events
- Enrichment API calls and results
- System errors and exceptions
- Performance metrics

### 4. Testing Requirements

**Test Coverage**:
- Aim for >80% code coverage
- Test all security-critical functions
- Include edge cases and malformed input tests

**Test Types**:
1. **Unit Tests**: Individual functions and classes
2. **Integration Tests**: Component interactions
3. **Security Tests**: Vulnerability scanning, penetration testing
4. **Performance Tests**: Load testing for data pipeline

**Testing Honeypot Services**:
- Create safe test environments
- Use mock attackers for testing
- Verify logging and data capture
- Test failure modes and recovery

### 5. Configuration Management

**Environment Variables**:
- Use `.env` files for local development (never commit these)
- Document all required environment variables in `.env.example`
- Use environment-specific configs (dev, staging, prod)

**Sensitive Data**:
- Never hardcode credentials, API keys, or secrets
- Use secrets management systems (HashiCorp Vault, AWS Secrets Manager, etc.)
- Implement key rotation mechanisms
- Document all required secrets in documentation

**Configuration Files**:
- Use YAML or JSON for configuration
- Include schema validation
- Provide sensible defaults
- Document all configuration options

### 6. Threat Intelligence Best Practices

**Data Enrichment**:
- Implement caching for external API calls (reduce costs and latency)
- Handle rate limiting gracefully
- Use multiple threat intel sources when possible
- Validate and normalize data from external sources

**Recommended Threat Intel Sources**:
- **AbuseIPDB**: IP reputation
- **VirusTotal**: File/URL/IP analysis
- **WHOIS**: Domain registration data
- **MaxMind GeoIP**: Geolocation data
- **MISP**: Threat sharing platform
- **AlienVault OTX**: Open threat exchange

**Data Storage**:
- Store raw logs separately from processed data
- Implement data retention policies
- Consider GDPR and privacy regulations (even for attacker data)
- Use time-series databases for metrics (InfluxDB, Prometheus)
- Use document stores for logs (Elasticsearch, MongoDB)

### 7. Development Workflow

**Branch Strategy**:
- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Individual features
- `hotfix/*`: Critical bug fixes
- `claude/*`: AI assistant development branches

**Commit Messages**:
```
<type>(<scope>): <short description>

<detailed description>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `security`

Example:
```
feat(honeypot): add SSH honeypot service

Implemented low-interaction SSH honeypot that logs authentication
attempts and captures attacker commands. Includes connection logging,
credential capture, and session recording.

Closes #123
```

**Pull Request Guidelines**:
- Include description of changes
- Reference related issues
- Ensure all tests pass
- Update documentation
- Add security considerations section for security-related changes

### 8. Deployment and Infrastructure

**Containerization**:
- Use Docker for all services
- Create multi-stage builds for smaller images
- Use non-root users in containers
- Scan images for vulnerabilities (Trivy, Snyk)

**Infrastructure as Code**:
- Define infrastructure using Terraform or similar
- Version control all infrastructure definitions
- Document deployment procedures
- Implement automated deployments

**Monitoring and Alerting**:
- Monitor honeypot availability
- Alert on processing pipeline failures
- Track data ingestion rates
- Monitor resource utilization
- Set up health checks for all services

### 9. Common Tasks and Patterns

**Adding a New Honeypot Service**:
1. Create service module in `honeypot/services/`
2. Implement connection handling and logging
3. Add configuration schema
4. Write unit and integration tests
5. Update deployment manifests
6. Document the service and its purpose

**Adding Threat Intel Enrichment**:
1. Create enrichment module in `threat_intel/enrichment/`
2. Implement API integration with error handling
3. Add caching layer
4. Handle rate limiting
5. Write tests with mock responses
6. Update pipeline configuration

**Creating Visualizations**:
1. Define data requirements
2. Create queries/aggregations
3. Design dashboard layout
4. Implement in visualization tool (Grafana/Kibana)
5. Export and version control configuration
6. Document dashboard usage

### 10. Documentation Standards

**Code Documentation**:
- Every module should have a module-level docstring
- Every function should have a docstring with:
  - Description of purpose
  - Args with types
  - Returns with types
  - Raises (exceptions that can be raised)
  - Example usage (for complex functions)

**Architecture Documentation**:
- Maintain architecture diagrams
- Document data flows
- Explain security boundaries
- Describe integration points

**Operational Documentation**:
- Deployment procedures
- Troubleshooting guides
- Incident response playbooks
- Configuration guides

### 11. Security Considerations for AI Assistants

**When Working on This Project**:

- **Analyze, Don't Execute**: You can analyze malicious code and payloads, but never execute them
- **Educational Purpose**: This is a defensive security research project
- **Responsible Disclosure**: Any vulnerabilities found should be documented and fixed
- **Ethical Use**: The honeypot is for research and threat detection, not for offensive operations

**Red Flags to Avoid**:
- Don't create backdoors or intentional vulnerabilities
- Don't implement features that could harm attackers (active defense is out of scope)
- Don't process or store personally identifiable information unnecessarily
- Don't create capabilities for attacking other systems

### 12. Performance Considerations

**Scalability**:
- Design for horizontal scaling
- Use async/await for I/O operations
- Implement proper queuing for data processing
- Cache frequently accessed data

**Resource Management**:
- Monitor memory usage for long-running processes
- Implement connection pooling for databases
- Use generators for processing large datasets
- Clean up resources properly (use context managers)

### 13. Key Libraries and Tools

**Python Libraries**:
- `asyncio`: Async network programming
- `logging`: Structured logging
- `pydantic`: Data validation
- `requests`/`httpx`: HTTP clients
- `sqlalchemy`: Database ORM
- `redis-py`: Caching
- `elasticsearch-py`: Log storage
- `paramiko`: SSH protocol implementation
- `scapy`: Packet manipulation (if needed)

**Tools**:
- **Docker & Docker Compose**: Containerization
- **Elasticsearch/Kibana**: Log storage and visualization
- **Grafana**: Metrics dashboards
- **Prometheus**: Metrics collection
- **Redis**: Caching and queuing
- **PostgreSQL/MongoDB**: Data storage

### 14. Current State and Next Steps

**Current Status**:
- Repository initialized
- README created with project vision

**Immediate Next Steps**:
1. Set up project structure (directories and base files)
2. Create development environment setup (Docker Compose)
3. Implement first honeypot service (SSH recommended)
4. Set up logging infrastructure
5. Create basic data pipeline
6. Implement IP enrichment
7. Set up basic visualization

### 15. Questions to Ask Before Implementing

When uncertain about implementation details, AI assistants should ask:

1. **Scope**: What specific attacker techniques should this honeypot detect?
2. **Infrastructure**: What deployment environment (cloud, on-prem, hybrid)?
3. **Scale**: Expected attack volume and data retention period?
4. **Integration**: Which threat intel feeds should be integrated?
5. **Visualization**: What metrics and insights are most important?
6. **Compliance**: Any regulatory or compliance requirements?

## Quick Reference

**File Locations**:
- Configuration: `config/`
- Logs: `logs/` (not committed to git)
- Tests: `tests/`
- Documentation: `docs/`

**Environment Setup**:
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Run tests
pytest tests/

# Start services
docker-compose up -d
```

**Useful Commands**:
```bash
# View honeypot logs
docker-compose logs -f honeypot

# Access database
docker-compose exec db psql -U user -d threatdb

# Run specific tests
pytest tests/unit/test_honeypot.py -v

# Check code coverage
pytest --cov=src tests/

# Lint code
flake8 src/
black src/
```

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [Honeypot Best Practices](https://www.sans.org/reading-room/whitepapers/)
- [Threat Intelligence Best Practices](https://www.misp-project.org/best-practices/)

---

**Last Updated**: 2025-11-19
**Maintained By**: Project Contributors
**For AI Assistants**: Follow these guidelines when contributing to this project. When in doubt, prioritize security and ask for clarification.
