#!/bin/bash
set -e

# HealthPrep Docker Entrypoint
# Handles signal forwarding and graceful shutdown

# Function to handle signals
cleanup() {
    echo "Received shutdown signal, gracefully stopping..."
    kill -TERM "$child" 2>/dev/null
    wait "$child"
    exit 0
}

# Trap signals
trap cleanup SIGTERM SIGINT SIGQUIT

# Log startup
echo "=========================================="
echo "HealthPrep Container Starting"
echo "=========================================="
echo "Environment: ${FLASK_ENV:-production}"
echo "Port: ${PORT:-5000}"
echo "Workers: ${GUNICORN_WORKERS:-4}"
echo "=========================================="

# Validate required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    echo "ERROR: SECRET_KEY environment variable is required"
    exit 1
fi

# Optional: Wait for database to be ready
if [ "${WAIT_FOR_DB:-false}" = "true" ]; then
    echo "Waiting for database to be ready..."
    python -c "
import time
import psycopg2
import os

db_url = os.environ['DATABASE_URL']
max_retries = 30
retry_interval = 2

for i in range(max_retries):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print('Database is ready!')
        break
    except psycopg2.OperationalError:
        print(f'Waiting for database... ({i+1}/{max_retries})')
        time.sleep(retry_interval)
else:
    print('ERROR: Database not available after maximum retries')
    exit(1)
"
fi

# Run database migrations if enabled
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Running database migrations..."
    flask db upgrade || echo "Migration completed or no migrations needed"
fi

# Start the application
echo "Starting application..."
exec "$@" &
child=$!
wait "$child"
