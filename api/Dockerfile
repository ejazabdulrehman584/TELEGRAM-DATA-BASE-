FROM python:3.11-slim

WORKDIR /app

# system deps (none heavy required)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code + data
COPY . /app
# data/tgdata.parquet must be copied next to this Dockerfile (see build_db.py output)

ENV PORT=8080
ENV TGDATA_PARQUET=/app/data/tgdata.parquet
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
