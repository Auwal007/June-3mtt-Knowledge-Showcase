# Azure Deployment Script for Video Subtitler App (PowerShell)
# Run this script to deploy your app to Azure

param(
    [string]$ResourceGroup = "video-subtitler-rg",
    [string]$AppName = "video-subtitler-app",
    [string]$PlanName = "video-subtitler-plan",
    [string]$Location = "East US",
    [string]$PythonVersion = "3.10"
)

Write-Host "🚀 Starting Azure deployment for Video Subtitler App..." -ForegroundColor Green

# Check if Azure CLI is installed
try {
    $azVersion = az version --output json | ConvertFrom-Json
    Write-Host "✅ Azure CLI version: $($azVersion.'azure-cli')" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure CLI is not installed. Please install it first." -ForegroundColor Red
    Write-Host "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    exit 1
}

# Login to Azure
Write-Host "🔐 Logging into Azure..." -ForegroundColor Blue
az login

# Create resource group
Write-Host "📦 Creating resource group..." -ForegroundColor Blue
az group create --name $ResourceGroup --location $Location

# Create App Service plan
Write-Host "🏗️  Creating App Service plan..." -ForegroundColor Blue
az appservice plan create `
    --name $PlanName `
    --resource-group $ResourceGroup `
    --sku P1V2 `
    --is-linux

# Create web app
Write-Host "🌐 Creating web app..." -ForegroundColor Blue
az webapp create `
    --resource-group $ResourceGroup `
    --plan $PlanName `
    --name $AppName `
    --runtime "PYTHON|$PythonVersion" `
    --deployment-local-git

# Configure app settings
Write-Host "⚙️  Configuring app settings..." -ForegroundColor Blue

# Prompt for OpenRouter API key
$OpenRouterApiKey = Read-Host "Enter your OpenRouter API key" -AsSecureString
$OpenRouterApiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($OpenRouterApiKey))

az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $AppName `
    --settings OPENROUTER_API_KEY="$OpenRouterApiKeyPlain"

# Configure startup command
az webapp config set `
    --resource-group $ResourceGroup `
    --name $AppName `
    --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 app:app"

# Enable logging
az webapp log config `
    --resource-group $ResourceGroup `
    --name $AppName `
    --application-logging filesystem `
    --level information

# Get deployment credentials
Write-Host "🔑 Getting deployment credentials..." -ForegroundColor Blue
$DeploymentUrl = az webapp deployment source config-local-git `
    --resource-group $ResourceGroup `
    --name $AppName `
    --query url -o tsv

Write-Host "✅ Azure resources created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Deployment Information:" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "App Name: $AppName" -ForegroundColor White
Write-Host "App URL: https://$AppName.azurewebsites.net" -ForegroundColor White
Write-Host "Deployment URL: $DeploymentUrl" -ForegroundColor White
Write-Host ""
Write-Host "🚀 To deploy your code:" -ForegroundColor Yellow
Write-Host "1. git remote add azure $DeploymentUrl" -ForegroundColor White
Write-Host "2. git push azure main" -ForegroundColor White
Write-Host ""
Write-Host "📊 To monitor your app:" -ForegroundColor Yellow
Write-Host "1. Visit Azure Portal: https://portal.azure.com" -ForegroundColor White
Write-Host "2. Navigate to your resource group: $ResourceGroup" -ForegroundColor White
Write-Host "3. Select your app: $AppName" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Alternative deployment using ZIP:" -ForegroundColor Yellow
Write-Host "Run: az webapp deployment source config-zip --resource-group $ResourceGroup --name $AppName --src deploy.zip" -ForegroundColor White
