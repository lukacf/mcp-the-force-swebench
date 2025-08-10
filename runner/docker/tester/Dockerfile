FROM python:3.11-slim

# basic utilities and docker client
RUN apt-get update && apt-get install -y git docker.io curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tester_service tester_service

# make sure Python can see our package
ENV PYTHONPATH=/app

EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8080/ready || exit 1

# Run with multiple workers and shorter keep-alive
CMD ["uvicorn", "tester_service.tester:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--timeout-keep-alive", "5"]