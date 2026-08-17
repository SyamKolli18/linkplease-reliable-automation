FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for psycopg2 compilation if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Default command stamps database migration 002 then starts web server
CMD ["sh", "-c", "python -m alembic stamp 002_add_dm_id_and_event_type && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
