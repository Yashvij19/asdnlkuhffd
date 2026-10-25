# ==============================================================================
# Multi-Stage Production Dockerfile for Wind Generation Forecast Monitor
# ==============================================================================

# ---------- Stage 1: Frontend Build ----------
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# ---------- Stage 2: Python Dependencies ----------
FROM python:3.11-slim AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY backend/requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------- Stage 3: Production Runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

# Non-root unprivileged container user
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Copy virtualenv from deps stage
COPY --from=deps /opt/venv /opt/venv

# Copy backend application source
COPY backend/app ./app

# Copy committed seed snapshot files for zero-config offline bootstrap
COPY backend/data/seed ./data/seed

# Copy compiled React frontend into static directory
COPY --from=frontend-builder /build/frontend/dist ./static

# Ensure data directory exists and assign permissions to non-root appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

# Container liveness health check probe
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
