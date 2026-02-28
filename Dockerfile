FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p logs output output/pending

# Expose API port
EXPOSE 8000

# Default command: run the FastAPI server
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
