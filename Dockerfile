# DropKit Production Container for Google Cloud Run / Firebase
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DROPKIT_ENV=production

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt qrcode

# Copy application code
COPY . .

# Run DB schema initialization
RUN python -m backend.db

# Expose HTTP port
EXPOSE 8080

# Start DropKit production daemon
CMD ["python", "backend/server.py"]
