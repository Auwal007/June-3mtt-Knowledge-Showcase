# Stage 1: Build with dependencies
FROM python:3.11-slim AS builder

# Set environment variables to reduce image size
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg gcc libffi-dev libsndfile1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Final image
FROM python:3.11-slim

ENV PATH="/venv/bin:$PATH"
WORKDIR /app

# Install runtime-only dependencies (ffmpeg for subtitle work)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /venv /venv

# Copy app source code
COPY . .

# Expose port
EXPOSE 8000

# Run using gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
