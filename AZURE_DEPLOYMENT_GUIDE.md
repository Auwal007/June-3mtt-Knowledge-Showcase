# Azure Deployment Guide for Video Subtitler App

## Overview
This guide will help you deploy your Flask video processing application to Azure App Service.

## Prerequisites
1. Azure account with an active subscription
2. Azure CLI installed on your local machine
3. Git repository (GitHub recommended for CI/CD)

## Step 1: Install Azure CLI
Download and install Azure CLI from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

## Step 2: Login to Azure
```bash
az login
```

## Step 3: Create Resource Group
```bash
az group create --name video-subtitler-rg --location "East US"
```

## Step 4: Create App Service Plan
```bash
az appservice plan create --name video-subtitler-plan --resource-group video-subtitler-rg --sku B1 --is-linux
```

## Step 5: Create Web App
```bash
az webapp create --resource-group video-subtitler-rg --plan video-subtitler-plan --name video-subtitler-app --runtime "PYTHON|3.10" --deployment-local-git
```

## Step 6: Configure App Settings
```bash
# Set your OpenRouter API key
az webapp config appsettings set --resource-group video-subtitler-rg --name video-subtitler-app --settings OPENROUTER_API_KEY="your_api_key_here"

# Set Python version
az webapp config set --resource-group video-subtitler-rg --name video-subtitler-app --linux-fx-version "PYTHON|3.10"

# Configure startup command
az webapp config set --resource-group video-subtitler-rg --name video-subtitler-app --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"
```

## Step 7: Install System Dependencies
Create a custom container or use Azure Container Registry if you need ffmpeg and other system dependencies.

### Option A: Deploy with Git
```bash
# Add Azure as a remote
git remote add azure https://video-subtitler-app.scm.azurewebsites.net:443/video-subtitler-app.git

# Deploy to Azure
git push azure main
```

### Option B: Deploy with ZIP
```bash
# Create deployment package
zip -r deploy.zip . -x "*.git*" "__pycache__/*" "*.pyc" "venv/*"

# Deploy ZIP file
az webapp deployment source config-zip --resource-group video-subtitler-rg --name video-subtitler-app --src deploy.zip
```

## Step 8: Configure Custom Domain (Optional)
```bash
# Add custom domain
az webapp config hostname add --webapp-name video-subtitler-app --resource-group video-subtitler-rg --hostname yourdomain.com
```

## Step 9: Monitor and Scale
- Use Azure Portal to monitor app performance
- Scale up/out based on usage patterns
- Set up Application Insights for detailed monitoring

## Important Notes for Video Processing

### 1. File Storage
- Azure App Service has limited local storage
- Consider using Azure Blob Storage for large files
- Current setup uses /tmp directory which is ephemeral

### 2. Memory and CPU Limits
- B1 tier has 1.75GB RAM and 1 CPU core
- Video processing is resource-intensive
- Consider upgrading to P1V2 or higher for production

### 3. Timeout Settings
- Default timeout is 230 seconds
- Video processing may take longer
- Configured gunicorn timeout to 600 seconds

### 4. ffmpeg Installation
Azure App Service Linux containers include ffmpeg by default, but you may need to verify:

```bash
# Check if ffmpeg is available (via SSH or App Service Console)
which ffmpeg
ffmpeg -version
```

If ffmpeg is not available, you'll need to:
1. Create a custom Docker container with ffmpeg
2. Use Azure Container Registry
3. Deploy as a container app

## Environment Variables Required
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `PORT`: Automatically set by Azure
- `WEBSITE_SITE_NAME`: Automatically set by Azure (used for environment detection)

## Monitoring URLs
- App URL: https://video-subtitler-app.azurewebsites.net
- SCM URL: https://video-subtitler-app.scm.azurewebsites.net
- Log Stream: Available in Azure Portal

## Troubleshooting
1. Check Application Logs in Azure Portal
2. Use Log Stream for real-time debugging
3. SSH into the container for advanced troubleshooting
4. Monitor resource usage and scale accordingly

## Alternative Deployment Options

### Docker Container Deployment
If you need full control over the environment:

1. Create a Dockerfile
2. Build and push to Azure Container Registry
3. Deploy as Web App for Containers

### Azure Functions
For lighter processing or event-driven scenarios:
- Consider breaking down the pipeline into smaller functions
- Use Azure Functions with blob triggers for file processing

## Cost Optimization
- Use Azure Cost Management to monitor spending
- Consider using Azure Functions for sporadic usage
- Set up auto-scaling policies
- Use cheaper storage tiers for temporary files

## Security Considerations
- Store API keys in Azure Key Vault
- Enable HTTPS only
- Configure CORS if needed for frontend
- Set up authentication if required
