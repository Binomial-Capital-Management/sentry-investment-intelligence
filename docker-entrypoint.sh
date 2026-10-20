#!/bin/bash
set -e

echo "🚀 Starting Sentry Backend..."

# Run database migrations if PostgreSQL is enabled
if [ "${ENABLE_POSTGRES:-false}" = "true" ]; then
    echo "📦 Checking database migrations..."
    
    # Wait for database to be ready (max 30 seconds)
    MAX_RETRIES=30
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if python -c "from core.database.postgres_client import get_postgres_rls_client; import asyncio; asyncio.run(get_postgres_rls_client())" 2>/dev/null; then
            echo "✅ Database connection ready"
            break
        fi
        RETRY=$((RETRY + 1))
        echo "⏳ Waiting for database... ($RETRY/$MAX_RETRIES)"
        sleep 1
    done
    
    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo "⚠️ Database not ready, skipping migrations"
    else
        # Run Alembic migrations
        echo "🔄 Running Alembic migrations..."
        if alembic upgrade head; then
            echo "✅ Migrations complete"
        else
            echo "⚠️ Migration failed, but continuing startup..."
            # Don't exit - let the app try to start anyway
            # The health check will fail if there's a real problem
        fi
    fi
else
    echo "ℹ️ PostgreSQL disabled, skipping migrations"
fi

# Initialize Canvas Fields DB if not exists
CANVAS_DB="${CANVAS_FIELDS_DB_PATH:-/mnt/efs/canvas/canvas_fields.db}"
if [ ! -f "$CANVAS_DB" ]; then
    echo "📊 Canvas fields database not found, initializing..."
    # Create directory if needed
    mkdir -p "$(dirname "$CANVAS_DB")"
    # Run discovery in background (takes a few minutes, don't block startup)
    nohup python scripts/discover_canvas_fields.py > /tmp/canvas_discovery.log 2>&1 &
    echo "🔄 Canvas fields discovery started in background (check /tmp/canvas_discovery.log)"
else
    echo "✅ Canvas fields database found"
fi

# Start the application
echo "🌐 Starting uvicorn with ${WEB_CONCURRENCY:-4} workers..."
exec python -m uvicorn app_fastapi:app --host 0.0.0.0 --port 8002 --workers ${WEB_CONCURRENCY:-4}
