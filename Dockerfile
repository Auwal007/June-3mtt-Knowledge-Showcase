# Use Python slim image instead of full Python
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only essential system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python packages with size optimizations
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    Flask==3.1.1 \
    requests \
    ffmpeg-python==0.2.0 \
    gunicorn \
    python-dotenv && \
    # Install PyTorch CPU-only version (much smaller than CUDA version)
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    # Install transformers and whisper
    pip install --no-cache-dir transformers openai-whisper && \
    # Clean up pip cache and temporary files
    pip cache purge && \
    find /usr/local -name '*.pyc' -delete && \
    find /usr/local -name '__pycache__' -delete

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p input output subs extracted_audio transcripts logs/openrouter_requests logs/openrouter_errors

# Remove unnecessary files to reduce image size
RUN find . -name "*.pyc" -delete && \
    find . -name "__pycache__" -delete && \
    find . -name "*.pyo" -delete

# Expose port (Railway uses PORT environment variable)
EXPOSE $PORT

# Use Railway's PORT environment variable
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 --workers 1 --max-requests 100 --max-requests-jitter 10 app:app