#!/bin/bash
set -e

echo "Starting Entrypoint Script..."

# Ensure Nginx temp directories exist for non-root user
mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

# Ensure we're in the backend directory for any DB checks/migrations
cd /app/backend

# Optional: Run any pre-flight database migrations here
# For example, if you use flask-migrate:
# echo "Running DB Migrations..."
# flask db upgrade || echo "Migration failed or not applicable, continuing..."

echo "Starting Supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
