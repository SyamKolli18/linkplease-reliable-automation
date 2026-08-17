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

# Default command runs web server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
