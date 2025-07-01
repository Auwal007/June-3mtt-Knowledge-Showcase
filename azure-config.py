# Azure App Service configuration
# This file configures the runtime environment

# Specify Python version
python_version = "3.10"

# Configure startup command
startup_file = "app.py"

# Environment variables can be set in Azure Portal
# Required environment variables:
# - OPENROUTER_API_KEY: Your OpenRouter API key

# File system paths for Azure App Service
# Azure App Service provides /tmp for temporary files
# but you may need to configure persistent storage for larger files

# Logging configuration
logging_level = "INFO"

# Port configuration (automatically set by Azure)
port = "$PORT"
