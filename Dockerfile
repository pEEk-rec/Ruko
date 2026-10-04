# One image runs everything: the web app is built in the first stage and the backend serves it.
# Build from the repository root:   docker build -t ruko .
# Run:                              docker run -p 8080:8080 -e PORT=8080 ruko
# Cloud Run sets PORT itself; see docs/deploy_cloud_run.md.

# --- Stage 1: build the web app ---
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# --- Stage 2: the backend, serving the built app ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RUKO_DATA_DIR=/app/data \
    RUKO_STATIC_DIR=/app/static \
    RUKO_ENVIRONMENT=prod

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

COPY data ./data
COPY --from=web /web/dist ./static

RUN useradd --create-home --uid 10001 ruko
USER ruko

EXPOSE 8000
CMD ["sh", "-c", "uvicorn ruko.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
