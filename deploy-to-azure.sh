#!/bin/bash

# Azure Deployment Script for Video Subtitler App
# Run this script to deploy your app to Azure

set -e

echo "🚀 Starting Azure deployment for Video Subtitler App..."

# Configuration
RESOURCE_GROUP="video-subtitler-rg"
APP_NAME="video-subtitler-app"
PLAN_NAME="video-subtitler-plan"
LOCATION="East US"
PYTHON_VERSION="3.10"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first."
    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login to Azure
echo "🔐 Logging into Azure..."
az login

# Create resource group
echo "📦 Creating resource group..."
az group create --name $RESOURCE_GROUP --location "$LOCATION"

# Create App Service plan
echo "🏗️  Creating App Service plan..."
az appservice plan create \
    --name $PLAN_NAME \
    --resource-group $RESOURCE_GROUP \
    --sku P1V2 \
    --is-linux

# Create web app
echo "🌐 Creating web app..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $PLAN_NAME \
    --name $APP_NAME \
    --runtime "PYTHON|$PYTHON_VERSION" \
    --deployment-local-git

# Configure app settings
echo "⚙️  Configuring app settings..."

# Prompt for OpenRouter API key
read -p "Enter your OpenRouter API key: " -s OPENROUTER_API_KEY
echo

az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings OPENROUTER_API_KEY="$OPENROUTER_API_KEY"

# Configure startup command
az webapp config set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 app:app"

# Enable logging
az webapp log config \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --application-logging filesystem \
    --level information

# Get deployment credentials
echo "🔑 Getting deployment credentials..."
DEPLOYMENT_URL=$(az webapp deployment source config-local-git \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --query url -o tsv)

echo "✅ Azure resources created successfully!"
echo ""
echo "📋 Deployment Information:"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $APP_NAME"
echo "App URL: https://$APP_NAME.azurewebsites.net"
echo "Deployment URL: $DEPLOYMENT_URL"
echo ""
echo "🚀 To deploy your code:"
echo "1. git remote add azure $DEPLOYMENT_URL"
echo "2. git push azure main"
echo ""
echo "📊 To monitor your app:"
echo "1. Visit Azure Portal: https://portal.azure.com"
echo "2. Navigate to your resource group: $RESOURCE_GROUP"
echo "3. Select your app: $APP_NAME"
echo ""
echo "🔧 Alternative deployment using ZIP:"
echo "Run: az webapp deployment source config-zip --resource-group $RESOURCE_GROUP --name $APP_NAME --src deploy.zip"
