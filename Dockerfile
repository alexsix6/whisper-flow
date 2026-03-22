FROM python:3.12-slim-bookworm

WORKDIR /app

# Server-only dependencies (minimal image)
COPY requirements-server.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-server.txt

# Copy only server code
COPY whisperflow/ ./whisperflow/

# Cloud Run sets PORT automatically; default 8181 for local dev
ENV PORT=8181

# Cloud Run requires listening on 0.0.0.0:$PORT
CMD exec uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port $PORT
