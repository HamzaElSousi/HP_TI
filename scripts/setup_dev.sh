#!/bin/bash
# Development environment setup script for HP_TI

set -e

echo "Setting up HP_TI development environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

echo "✓ Python version OK ($python_version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install production dependencies
echo "Installing production dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created (please edit with your settings)"
else
    echo "✓ .env file already exists"
fi

# Create log directories
echo "Creating log directories..."
mkdir -p logs/honeypots
mkdir -p logs/pipeline
mkdir -p logs/enrichment
echo "✓ Log directories created"

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install
echo "✓ Pre-commit hooks installed"

# Run initial code formatting
echo "Running initial code formatting..."
black honeypot/ threat_intel/ pipeline/ tests/ || true
isort honeypot/ threat_intel/ pipeline/ tests/ || true
echo "✓ Code formatted"

# Run tests to verify setup
echo "Running tests to verify setup..."
pytest tests/unit/ -v || echo "⚠ Some tests failed (this is OK for initial setup)"

echo ""
echo "=========================================="
echo "Development environment setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your configuration"
echo "  2. Activate virtual environment: source venv/bin/activate"
echo "  3. Run tests: pytest"
echo "  4. Start honeypot: python main.py"
echo "  5. Or use Docker: cd deployment/docker && docker-compose up"
echo ""
