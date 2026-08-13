#!/bin/bash
set -e

echo "Starting Entrypoint Script..."

# Ensure Nginx temp directories exist for non-root user
mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

# Ensure we're in the backend directory for any DB checks/migrations
cd /app/backend

# Run one-time database migrations before starting supervisor
echo "Running database migrations..."
python -c "from app import app; from utils.db_migrations import run_pending_migrations; run_pending_migrations(app)" || echo "Migration failed, continuing..."

echo "Starting Supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
