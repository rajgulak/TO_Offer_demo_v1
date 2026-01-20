# API Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Copy requirements first for caching
COPY api/requirements.txt ./api/

# Install requirements with increased timeout and retries
# Split into smaller batches to avoid timeout on large packages
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    fastapi>=0.109.0 \
    uvicorn>=0.27.0 \
    sse-starlette>=1.8.0 \
    pydantic>=2.0.0 \
    python-dotenv>=1.0.0 \
    requests>=2.31.0

# Install LangChain dependencies separately (larger packages)
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    langgraph>=0.2.0 \
    langchain>=0.3.0 \
    langchain-core>=0.3.0

# Install LLM provider packages
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    langchain-anthropic>=0.3.0 \
    langchain-openai>=0.2.0

# Copy the rest of the application
COPY agents/ ./agents/
COPY tools/ ./tools/
COPY data/ ./data/
COPY config/ ./config/
COPY infrastructure/ ./infrastructure/
COPY api/ ./api/

# Expose port
EXPOSE 8000

# Run the API
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
