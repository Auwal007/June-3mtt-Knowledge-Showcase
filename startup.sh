#!/bin/bash

# Azure App Service startup script
# This script runs when the container starts

echo "Starting Azure App Service..."

# Create necessary directories
mkdir -p /home/site/wwwroot/input
mkdir -p /home/site/wwwroot/output
mkdir -p /home/site/wwwroot/subs
mkdir -p /home/site/wwwroot/extracted_audio
mkdir -p /home/site/wwwroot/transcripts
mkdir -p /home/site/wwwroot/logs/openrouter_requests
mkdir -p /home/site/wwwroot/logs/openrouter_errors

# Set permissions
chmod -R 755 /home/site/wwwroot/

# Install system dependencies if needed
# apt-get update && apt-get install -y ffmpeg

echo "Directories created and permissions set."

# Start the application
echo "Starting Flask application..."
# Start the Flask application using Gunicorn
exec gunicorn --bind 0.0.0.0:8000 --timeout 600 --workers 1 --max-requests 1000 app:app
