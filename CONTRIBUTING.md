# Contributing to HP_TI

Thank you for your interest in contributing to the HP_TI (Honeypot & Threat Intelligence) project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Security Considerations](#security-considerations)

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Focus on constructive feedback
- Prioritize security and user safety
- Collaborate openly and transparently
- Give credit where due

### Unacceptable Behavior

- Harassment or discriminatory language
- Publishing others' private information
- Intentionally introducing vulnerabilities
- Using the project for malicious purposes

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose
- Git
- Basic understanding of honeypots and threat intelligence
- Security mindset

### First Steps

1. **Fork the repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/HP_TI.git
   cd HP_TI
   ```

2. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt

   # Set up pre-commit hooks
   pre-commit install
   ```

3. **Configure environment**
   ```bash
   # Copy example environment file
   cp .env.example .env

   # Edit .env with your settings
   nano .env
   ```

4. **Run tests**
   ```bash
   # Ensure everything works
   pytest tests/
   ```

## Development Environment

### Directory Structure

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the complete project structure.

### Required Tools

- **Python 3.9+**: Primary development language
- **Docker**: For running services in isolation
- **Make**: For common development tasks (optional)
- **Git**: Version control

### Optional but Recommended

- **VS Code** with Python extension
- **PyCharm** Community or Professional
- **Docker Desktop** for easier container management
- **Postman** for API testing

### Environment Variables

See [.env.example](.env.example) for all required environment variables.

Key variables:
- `HONEYPOT_SSH_PORT`: SSH honeypot listening port
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `DATABASE_URL`: PostgreSQL connection string
- `ELASTICSEARCH_URL`: Elasticsearch endpoint
- `REDIS_URL`: Redis connection string

## How to Contribute

### Types of Contributions

We welcome:

1. **Bug Reports**: Found a bug? Open an issue with details
2. **Feature Requests**: Have an idea? Discuss it in an issue first
3. **Documentation**: Improvements, clarifications, examples
4. **Code**: Bug fixes, features, optimizations
5. **Tests**: Additional test coverage
6. **Security**: Vulnerability reports (see security policy)

### Before You Start

1. **Check existing issues**: Avoid duplicate work
2. **Discuss major changes**: Open an issue to discuss approach
3. **Read documentation**: Understand the architecture and goals
4. **Review CLAUDE.md**: Understand project conventions

### Workflow

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes**
   - Write code following our standards
   - Add/update tests
   - Update documentation
   - Run tests locally

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat(honeypot): add HTTP honeypot service"
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request**
   - Use the PR template
   - Link related issues
   - Provide clear description

## Coding Standards

### Python Style

We follow **PEP 8** with some specific guidelines:

- **Line length**: 88 characters (Black formatter default)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings (Black default)
- **Imports**: Sorted with isort

### Code Formatting

We use automated formatters:

```bash
# Format code with Black
black honeypot/ threat_intel/ pipeline/

# Sort imports with isort
isort honeypot/ threat_intel/ pipeline/

# Lint with flake8
flake8 honeypot/ threat_intel/ pipeline/

# Type check with mypy
mypy honeypot/ threat_intel/ pipeline/
```

**Pre-commit hooks will run these automatically.**

### Type Hints

Always use type hints for function signatures:

```python
from typing import Dict, List, Optional

def process_log_entry(
    entry: Dict[str, Any],
    enrichment_enabled: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Process a log entry and optionally enrich it.

    Args:
        entry: Log entry dictionary
        enrichment_enabled: Whether to enrich the entry

    Returns:
        Processed entry or None if invalid

    Raises:
        ValueError: If entry is malformed
    """
    pass
```

### Docstrings

Use **Google style** docstrings:

```python
def calculate_threat_score(
    ip: str,
    abuse_score: int,
    attack_count: int
) -> float:
    """Calculate threat score for an IP address.

    Combines multiple factors to produce a normalized threat score
    between 0 and 100.

    Args:
        ip: IP address to score
        abuse_score: AbuseIPDB confidence score (0-100)
        attack_count: Number of attacks from this IP

    Returns:
        Threat score between 0 and 100

    Raises:
        ValueError: If abuse_score is outside valid range

    Example:
        >>> calculate_threat_score("192.168.1.1", 75, 10)
        82.5
    """
    pass
```

### Naming Conventions

- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

```python
# Good
MAX_RETRY_ATTEMPTS = 3
class ThreatIntelligenceEnricher:
    def __init__(self):
        self._cache = {}

    def enrich_ip(self, ip_address: str) -> dict:
        pass

# Bad
maxRetryAttempts = 3
class threat_intelligence_enricher:
    def EnrichIP(self, IPAddress: str) -> dict:
        pass
```

### Error Handling

Always handle errors explicitly:

```python
# Good
try:
    response = requests.get(url, timeout=5)
    response.raise_for_status()
except requests.Timeout:
    logger.warning(f"Timeout fetching {url}")
    return None
except requests.HTTPError as e:
    logger.error(f"HTTP error for {url}: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise

# Bad
try:
    response = requests.get(url)
except:
    pass
```

### Logging

Use structured logging with appropriate levels:

```python
import logging

logger = logging.getLogger(__name__)

# Good
logger.info(
    "SSH authentication attempt",
    extra={
        "source_ip": "192.168.1.1",
        "username": "admin",
        "success": False
    }
)

# Also acceptable for simple cases
logger.warning(f"Failed to enrich IP {ip_address}: rate limit exceeded")

# Bad
print("Authentication failed")  # Never use print for logging
```

## Testing Guidelines

### Test Requirements

- **Minimum coverage**: 80% overall
- **Critical paths**: 100% coverage for security-critical code
- **All new features**: Must include tests
- **Bug fixes**: Add regression test

### Test Structure

```
tests/
├── unit/              # Fast, isolated tests
│   ├── test_ssh_honeypot.py
│   ├── test_parsers.py
│   └── test_enrichers.py
├── integration/       # Tests with external dependencies
│   ├── test_pipeline.py
│   └── test_storage.py
├── security/          # Security-specific tests
│   └── test_isolation.py
└── fixtures/          # Shared test data
    └── sample_logs.json
```

### Writing Tests

Use **pytest** with fixtures:

```python
import pytest
from honeypot.services.ssh_honeypot import SSHHoneypot

@pytest.fixture
def ssh_honeypot():
    """Create SSH honeypot instance for testing."""
    honeypot = SSHHoneypot(port=2222)
    yield honeypot
    honeypot.stop()

def test_auth_attempt_logging(ssh_honeypot):
    """Test that authentication attempts are logged correctly."""
    # Arrange
    username = "admin"
    password = "password123"

    # Act
    result = ssh_honeypot.handle_auth_attempt(username, password)

    # Assert
    assert result is False  # Auth should fail
    assert ssh_honeypot.get_log_count() == 1
    log_entry = ssh_honeypot.get_last_log()
    assert log_entry["username"] == username
    assert log_entry["password"] == password
    assert log_entry["success"] is False
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_ssh_honeypot.py

# Run with coverage
pytest --cov=honeypot --cov-report=html tests/

# Run only unit tests
pytest tests/unit/

# Run with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_ssh_honeypot.py::test_auth_attempt_logging
```

### Mocking External Services

Always mock external API calls:

```python
from unittest.mock import patch, MagicMock

def test_ip_enrichment_with_abuseipdb():
    """Test IP enrichment using AbuseIPDB API."""
    # Arrange
    mock_response = {
        "data": {
            "abuseConfidenceScore": 75,
            "countryCode": "CN",
            "isWhitelisted": False
        }
    }

    # Act
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.status_code = 200

        enricher = AbuseIPDBEnricher(api_key="test_key")
        result = enricher.enrich("192.168.1.1")

    # Assert
    assert result["abuse_score"] == 75
    assert result["country"] == "CN"
    mock_get.assert_called_once()
```

## Commit Message Guidelines

We follow **Conventional Commits**:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `security`: Security improvements
- `perf`: Performance improvements

### Scope

The component affected:
- `honeypot`: Honeypot services
- `pipeline`: Data pipeline
- `enrichment`: Threat intelligence enrichment
- `storage`: Database/storage
- `visualization`: Dashboards and reporting
- `deployment`: Infrastructure and deployment
- `tests`: Testing infrastructure

### Examples

```
feat(honeypot): add HTTP honeypot service

Implemented low-interaction HTTP honeypot that simulates
common admin panels and detects web-based attacks.

Features:
- Fake WordPress admin panel
- SQL injection detection
- XSS attempt logging

Closes #42
```

```
fix(enrichment): handle AbuseIPDB rate limiting

Added exponential backoff retry logic when hitting
rate limits. Caches errors to avoid repeated failures.

Fixes #67
```

```
docs(architecture): update system architecture diagram

Added new components from Phase 4 implementation.

[skip ci]
```

```
security(honeypot): fix command injection vulnerability

Sanitize all user input before logging to prevent
command injection in log processing pipeline.

BREAKING CHANGE: Log format changed to escape special characters

Fixes #SECURITY-001
```

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Added tests for new features
- [ ] Updated documentation
- [ ] Commit messages follow convention
- [ ] No merge conflicts
- [ ] Security considerations documented (if applicable)

### PR Template

Use this template for your pull request:

```markdown
## Description
Brief description of changes

## Related Issues
Closes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Security Considerations
Any security implications?

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated checks**: Must pass CI/CD
2. **Code review**: At least one approval required
3. **Security review**: Required for security-related changes
4. **Documentation review**: For docs changes
5. **Maintainer approval**: For merging

### After Approval

- Maintainer will merge (usually squash merge)
- Delete your branch after merge
- Close related issues if not auto-closed

## Security Considerations

### Security-First Development

This is a **security research project**. Every contribution must prioritize security:

1. **Never introduce vulnerabilities**
   - No SQL injection, command injection, XSS, etc.
   - Validate and sanitize all inputs
   - Use parameterized queries
   - Escape output appropriately

2. **Honeypot isolation**
   - Honeypots must not be exploitable
   - No real shells or system access
   - Containerization is mandatory
   - Network isolation required

3. **Data sanitization**
   - Treat all attacker data as hostile
   - Sanitize before processing
   - Never execute attacker-provided code
   - Be cautious with file operations

4. **Secrets management**
   - Never commit secrets or credentials
   - Use environment variables
   - Document required secrets
   - Rotate secrets regularly

### Reporting Security Vulnerabilities

**DO NOT** open public issues for security vulnerabilities.

Instead:
1. Email security contact (if defined in README)
2. Provide detailed description
3. Include proof of concept if possible
4. Allow reasonable time for fix before disclosure

### Security Review Checklist

For security-related PRs, ensure:

- [ ] No hardcoded credentials
- [ ] All inputs validated
- [ ] Outputs escaped/sanitized
- [ ] SQL queries parameterized
- [ ] File operations sanitized
- [ ] Error messages don't leak sensitive info
- [ ] Logging doesn't include secrets
- [ ] Container isolation maintained
- [ ] Network boundaries respected

## Questions or Need Help?

- **Documentation**: Check [CLAUDE.md](CLAUDE.md) and [docs/](docs/)
- **Issues**: Search existing issues or open a new one
- **Discussions**: Use GitHub Discussions for questions
- **Architecture**: See [docs/architecture/](docs/architecture/)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

---

**Thank you for contributing to HP_TI!**

Making the internet safer, one honeypot at a time. 🍯🐝
