# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building wheels (psycopg2, spacy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip + hatch
RUN pip install --no-cache-dir hatchling pip --upgrade

# Copy dependency spec first for layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install runtime dependencies
RUN pip install --no-cache-dir ".[dev]"

# Download spacy model for Presidio NLP (en_core_web_sm is ~12MB)
RUN python -m spacy download en_core_web_sm --quiet || true

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Non-root user for security
RUN groupadd -r modeltoll && useradd -r -g modeltoll modeltoll

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Set ownership
RUN chown -R modeltoll:modeltoll /app

USER modeltoll

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
