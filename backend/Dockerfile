# Legal RAG Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command for development (replace with FastAPI later in Phase 4)
CMD ["python", "-m", "app.main"]
