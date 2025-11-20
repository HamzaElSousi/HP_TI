# HP_TI Honeypot Dockerfile
# Multi-stage build for minimal production image

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies to a local directory
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash honeypot

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/honeypot/.local

# Copy application code
COPY honeypot/ /app/honeypot/
COPY threat_intel/ /app/threat_intel/
COPY pipeline/ /app/pipeline/
COPY config/ /app/config/
COPY main.py /app/
COPY __init__.py /app/

# Create log directory
RUN mkdir -p /app/logs/honeypots && \
    chown -R honeypot:honeypot /app

# Switch to non-root user
USER honeypot

# Add local bin to PATH
ENV PATH=/home/honeypot/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Expose honeypot ports
EXPOSE 2222 8080 8443 2323 2121

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*main.py" || exit 1

# Run honeypot
CMD ["python", "-u", "main.py"]
