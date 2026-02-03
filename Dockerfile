# HealthPrep AWS ECS Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies and apply security updates
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, wheel, and setuptools to latest versions for security patches
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Copy dependency files (requirements.txt generated from pyproject.toml via uv pip compile)
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Upgrade any vulnerable packages post-install (CVE fixes)
RUN pip install --no-cache-dir --upgrade wheel>=0.46.2 jaraco.context>=6.1.0

# Stage 2: Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=5000

WORKDIR /app

# Install runtime dependencies including Tesseract OCR and apply security updates (CVE patches for openssl)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Verify OpenSSL version and log for security audit (CVE-2025-69419, CVE-2025-69420, CVE-2025-69421)
# Note: apt-get upgrade pulls latest available from Debian repos; version depends on base image currency
RUN echo "=== OS Security Package Versions ===" && \
    openssl version -a && \
    dpkg -l | grep -E "(libssl|openssl|libexpat|libsqlite)" || true && \
    echo "=== End OS Package Audit ==="

# Upgrade pip/wheel/setuptools in production stage for security
RUN pip install --no-cache-dir --upgrade pip wheel>=0.46.2 setuptools

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Re-apply security upgrades after copying packages (ensures CVE fixes override builder versions)
# Pin exact minimum versions to ensure CVE patches (wheel CVE-2026-24049, jaraco.context CVE-2026-23949)
RUN pip install --no-cache-dir --upgrade "wheel>=0.46.2" "jaraco.context>=6.1.0"

# Verify security patches are applied - fail build if versions are not sufficient
RUN echo "Verifying security patches..." && \
    openssl version && \
    WHEEL_VER=$(pip show wheel 2>/dev/null | grep "^Version:" | awk '{print $2}') && \
    JARACO_VER=$(pip show jaraco.context 2>/dev/null | grep "^Version:" | awk '{print $2}') && \
    echo "wheel version: $WHEEL_VER" && \
    echo "jaraco.context version: $JARACO_VER" && \
    python3 -c "from packaging.version import Version; assert Version('$WHEEL_VER') >= Version('0.46.2'), 'wheel CVE-2026-24049 not patched'" && \
    python3 -c "from packaging.version import Version; assert Version('$JARACO_VER') >= Version('6.1.0'), 'jaraco.context CVE-2026-23949 not patched'" && \
    echo "Security patches verified successfully"

# Create non-root user for security
RUN groupadd -r healthprep && useradd -r -g healthprep healthprep

# Copy application code
COPY --chown=healthprep:healthprep . .

# Remove development files that shouldn't be in production
RUN rm -rf \
    .git \
    .gitignore \
    .replit \
    replit.nix \
    attached_assets \
    archive \
    docs \
    __pycache__ \
    *.pyc \
    .pytest_cache \
    .coverage

# Switch to non-root user
USER healthprep

# Expose port
EXPOSE 5000

# Health check (using the API health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Start command using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "50", "main:app"]
