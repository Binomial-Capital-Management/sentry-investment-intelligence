# Multi-stage build for production deployment
# Using Python 3.12 Debian
# Updated: 2025-11-15 - Playwright/Chromium removed (archived, replaced by Gamma API)
FROM --platform=linux/amd64 python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    linux-libc-dev \
    git \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    pkg-config \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and local packages needed for install
COPY requirements.txt .
COPY binomialhash/ ./binomialhash/

# Upgrade pip to latest version for better dependency resolution
RUN pip install --upgrade pip

# Install Python dependencies using legacy resolver to avoid backtracking issues
RUN pip install --user --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

# Production stage
FROM --platform=linux/amd64 python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    # ARCHIVED: Playwright Chromium dependencies (replaced by Gamma API, see pdf-archive/)
    # libnss3 \
    # libnspr4 \
    # libatk1.0-0 \
    # libatk-bridge2.0-0 \
    # libcups2 \
    # libdrm2 \
    # libdbus-1-3 \
    # libxkbcommon0 \
    # libxcomposite1 \
    # libxdamage1 \
    # libxfixes3 \
    # libxrandr2 \
    # libgbm1 \
    # libpango-1.0-0 \
    # libcairo2 \
    # libasound2 \
    # libatspi2.0-0 \
    # libfreetype6 \
    # libfreetype6-dev \
    # libharfbuzz0b \
    # fonts-freefont-ttf \
    # SciPy/NumPy/CVXPy runtime deps
    gfortran \
    libopenblas0 \
    liblapack3 \
    libstdc++6 \
    # XML processing for lxml/beautifulsoup4
    libxml2 \
    libxslt1.1 \
  && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --uid 1000 --create-home appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder (ensure correct ownership)
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# ARCHIVED: Playwright browser installation (replaced by Gamma API, see pdf-archive/)
# ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# RUN mkdir -p /ms-playwright && chown -R appuser:appuser /ms-playwright
# ENV PATH="/home/appuser/.local/bin:$PATH"
# ENV PYTHONPATH="/home/appuser/.local/lib/python3.12/site-packages:$PYTHONPATH"
# RUN python -m playwright install chromium

# Set PATH for user binaries
ENV PATH="/home/appuser/.local/bin:$PATH"
ENV PYTHONPATH="/home/appuser/.local/lib/python3.12/site-packages:$PYTHONPATH"

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure data directory exists with proper permissions
RUN mkdir -p /app/core/mcp_servers/fmp/data && \
    chown -R appuser:appuser /app/core/mcp_servers/fmp/data

# NOTE: Field mappings DB is pre-built locally and committed to repo
# To rebuild: python scripts/build_complete_field_mappings.py
# Then commit: git add core/mcp_servers/fmp/data/field_mappings.db

# NOTE: Ticker universe is populated directly against RDS at runtime or via separate migration
# To populate: python scripts/populate_ticker_universe.py (requires DATABASE_URL)
# Or run as post-deployment step

# Ensure baked DBs are writable by runtime user
RUN chown -R appuser:appuser /app/core/mcp_servers/fmp/data 2>/dev/null || true

# Make sure scripts are executable
RUN chmod +x /app/run_dev.sh 2>/dev/null || true
RUN chmod +x /app/docker-entrypoint.sh 2>/dev/null || true

# Create data directories for SQLite databases (writable by appuser)
# Also create mount point for EFS (will be used in production)
RUN mkdir -p /tmp/data/state /tmp/data/sessions /tmp/data/conversations /tmp/data/canvas && \
    mkdir -p /mnt/efs/state /mnt/efs/sessions /mnt/efs/conversations /mnt/efs/canvas && \
    chown -R appuser:appuser /tmp/data && \
    chown -R appuser:appuser /mnt/efs 2>/dev/null || true

# Switch to non-root user
USER appuser

# Add user's local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app:/home/appuser/.local/lib/python3.12/site-packages
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# ARCHIVED: Playwright browsers path (replaced by Gamma API, see pdf-archive/)
# ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Database paths will be set by environment file from S3
# Fallback paths only if env file doesn't load
# ENV LANGGRAPH_DB_PATH=/tmp/data/state/langgraph_state.db
# ENV OPENAI_SESSIONS_DB_PATH=/tmp/data/sessions/binomial_sessions.db
# ENV CONVERSATION_DB_PATH=/tmp/data/conversations/conversation_messages.db

# Health check - generous timeout for heavy AI/LLM/risk workloads
# interval=60s: check less frequently to reduce overhead during heavy compute
# timeout=60s: allows workers to finish Monte Carlo/LLM calls before responding
# start-period=120s: gives app time to fully initialize (load models, connect to DB/Redis/warm caches)
# retries=5: more tolerance before marking unhealthy
HEALTHCHECK --interval=60s --timeout=60s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8002/v6/health || exit 1

# Expose port
EXPOSE 8002

# Start the application - always use port 8002 internally
# Workers configurable via WEB_CONCURRENCY env var
# Recommended: 2-4 workers for async I/O-bound workloads (LLM calls, DB queries)
# Override in AWS: Set WEB_CONCURRENCY in ECS task definition or S3 env file
ENV WEB_CONCURRENCY=4

# Use entrypoint script that runs migrations before starting app
CMD ["/app/docker-entrypoint.sh"]
