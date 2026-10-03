FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RUKO_DATA_DIR=/app/data \
    RUKO_ENVIRONMENT=prod

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

COPY data ./data

RUN useradd --create-home --uid 10001 ruko
USER ruko

EXPOSE 8000
CMD ["sh", "-c", "uvicorn ruko.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
