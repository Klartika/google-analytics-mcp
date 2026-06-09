# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Install only the package and its dependencies. We deliberately do NOT copy the
# tests/ directory so setuptools flat-layout auto-discovery resolves a single
# top-level package (analytics_mcp).
COPY pyproject.toml README.md ./
COPY analytics_mcp ./analytics_mcp

RUN pip install .

# Run as a non-root user. Pre-create the token-DB directory owned by that user:
# a freshly-created Docker named volume inherits this ownership, so the non-root
# process can write the SQLite DB (TOKEN_DB_PATH defaults to /data/tokens.db).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

USER appuser

# Persisted token store (mount a volume here in production).
VOLUME ["/data"]

EXPOSE 8080

# Streamable HTTP entry point defined in pyproject [project.scripts].
CMD ["analytics-mcp-http"]
