# HealthPrep - Production Dockerfile
# Multi-stage build for optimized image size

# =============================================================================
# Stage 1: Build dependencies
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels -e .

# =============================================================================
# Stage 2: Production image
# =============================================================================
FROM python:3.11-slim as production

# Security: Run as non-root user
RUN groupadd -r healthprep && useradd -r -g healthprep healthprep

WORKDIR /app

# Install runtime dependencies
# - tesseract-ocr: OCR processing for medical documents
# - poppler-utils: PDF processing (pdf2image)
# - libpq5: PostgreSQL client library
# - libgl1: OpenCV dependency
# - libglib2.0-0: System library
# - fonts: WeasyPrint PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpq5 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY --chown=healthprep:healthprep . .

# Remove development files (if any slipped through)
RUN rm -rf .cache __pycache__ *.pyc .git .env .env.* tests/

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs /app/instance && \
    chown -R healthprep:healthprep /app

# Switch to non-root user
USER healthprep

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

# Health check for ALB
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 5000

# Entrypoint
COPY --chown=healthprep:healthprep docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main:app"]
