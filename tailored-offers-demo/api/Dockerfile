# API Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY api/requirements.txt ./api/
RUN pip install --no-cache-dir -r api/requirements.txt

# Copy the rest of the application
COPY agents/ ./agents/
COPY tools/ ./tools/
COPY data/ ./data/
COPY config/ ./config/
COPY api/ ./api/

# Expose port
EXPOSE 8000

# Run the API
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
