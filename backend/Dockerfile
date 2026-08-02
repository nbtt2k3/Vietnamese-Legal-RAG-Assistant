FROM python:3.11-slim

WORKDIR /app

# OCR and PyTorch runtime dependencies. Keep the image non-interactive and
# remove apt metadata so the API image remains reproducible and smaller.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=3)"

# Start the ASGI API server. app.main is the CLI and must not be used as the
# container entrypoint.
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
