# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the Python Backend & Combine
FROM python:3.10-slim-bookworm

# Install system dependencies including Nginx and Supervisor
# Also installing dependencies for mysqlclient and playwright
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application securely
RUN useradd -r -m -d /app appuser

WORKDIR /app

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir numpy pandas \
    && pip install --no-cache-dir playwright cryptography lxml \
    && pip install --no-cache-dir -r /app/backend/requirements.txt \
    && pip install --no-cache-dir gunicorn gevent

# Install Playwright browsers (if needed by scrapers)
RUN playwright install --with-deps chromium

# Copy frontend build from stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy backend source code
COPY backend /app/backend

# Copy configurations
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh

# Set up permissions for non-root user
# Nginx needs to write to these directories
RUN mkdir -p /var/log/supervisor /var/run /var/log/nginx /var/lib/nginx/body /var/lib/nginx/fastcgi /var/lib/nginx/proxy /var/lib/nginx/scgi /var/lib/nginx/uwsgi \
    && chown -R appuser:appuser /app /var/log/supervisor /var/run /var/log/nginx /var/lib/nginx /etc/nginx \
    && chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose Nginx port
EXPOSE 8080

# Health check to ensure Nginx and the backend are responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/api/health || exit 1

# Start Supervisor via Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
