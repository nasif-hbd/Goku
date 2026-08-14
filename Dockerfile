FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY steward/ ./steward/
COPY scripts/ ./scripts/

# Cloud Run sets $PORT; honour it rather than hardcoding.
CMD exec uvicorn steward.main:app --host 0.0.0.0 --port ${PORT}
