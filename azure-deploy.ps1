# ============================================================
# azure-deploy.ps1 — Deploy the Discord Bot to Azure Container Apps
# Run this in PowerShell as Administrator after:
#   1. Docker Desktop is running
#   2. Run: az login
# ============================================================

$ErrorActionPreference = "Stop"

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
$RESOURCE_GROUP      = "discord-bot-rg"
$LOCATION            = "centralindia"
$ACR_NAME            = "advdiscordbotacr$(Get-Random -Maximum 9999)"  # unique name
$CONTAINER_APP_NAME  = "advanced-discord-bot"
$CONTAINER_APP_ENV   = "discord-bot-env"
$IMAGE_NAME          = "advanced-discord-bot"
$IMAGE_TAG           = "latest"
$STORAGE_ACCOUNT     = "botdata$(Get-Random -Maximum 9999)"

# ── Load secrets from .env ─────────────────────────────────────────────────────
$envFile = Get-Content ".env" | Where-Object { $_ -match "=" }
$envVars = @{}
foreach ($line in $envFile) {
    $parts = $line -split "=", 2
    $key   = $parts[0].Trim()
    $value = $parts[1].Trim()
    $envVars[$key] = $value
}

$DISCORD_TOKEN = $envVars["DISCORD_TOKEN"]
$GROQ_API_KEY  = $envVars["GROQ_API_KEY"]
$OWNER_IDS     = $envVars["OWNER_IDS"]

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Advanced Discord Bot — Azure Deployment" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Register providers ────────────────────────────────────────────────
Write-Host "[1/9] Registering Azure providers..." -ForegroundColor Yellow
az provider register --namespace Microsoft.App --wait | Out-Null
az provider register --namespace Microsoft.OperationalInsights --wait | Out-Null
az provider register --namespace Microsoft.ContainerRegistry --wait | Out-Null
Write-Host "      Providers registered." -ForegroundColor Green

# ── Step 2: Create Resource Group ─────────────────────────────────────────────
Write-Host "[2/9] Creating Resource Group '$RESOURCE_GROUP'..." -ForegroundColor Yellow
az group create --name $RESOURCE_GROUP --location $LOCATION --output table
Write-Host "      Resource Group created." -ForegroundColor Green

# ── Step 3: Create Azure Container Registry ────────────────────────────────────
Write-Host "[3/9] Creating Container Registry '$ACR_NAME'..." -ForegroundColor Yellow
az acr create `
  --resource-group $RESOURCE_GROUP `
  --name $ACR_NAME `
  --sku Basic `
  --admin-enabled true `
  --output table
Write-Host "      Registry created." -ForegroundColor Green

# ── Step 4: Build & push image via ACR Build ──────────────────────────────────
Write-Host "[4/9] Building Docker image with FFmpeg and pushing to ACR..." -ForegroundColor Yellow
Write-Host "      This may take 3-5 minutes..." -ForegroundColor Gray
az acr build `
  --registry $ACR_NAME `
  --image "${IMAGE_NAME}:${IMAGE_TAG}" `
  --platform linux/amd64 `
  .
Write-Host "      Image built and pushed." -ForegroundColor Green

# ── Step 5: Get ACR credentials ───────────────────────────────────────────────
Write-Host "[5/9] Getting registry credentials..." -ForegroundColor Yellow
$ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv
$ACR_USERNAME     = az acr credential show --name $ACR_NAME --query username -o tsv
$ACR_PASSWORD     = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
Write-Host "      Credentials retrieved." -ForegroundColor Green

# ── Step 6: Create Container Apps Environment ─────────────────────────────────
Write-Host "[6/9] Creating Container Apps Environment..." -ForegroundColor Yellow
az containerapp env create `
  --name $CONTAINER_APP_ENV `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --output table
Write-Host "      Environment created." -ForegroundColor Green

# ── Step 7: Create persistent storage ─────────────────────────────────────────
Write-Host "[7/9] Creating Azure Storage for bot data (SQLite + guild configs)..." -ForegroundColor Yellow
az storage account create `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --output table

$STORAGE_KEY = az storage account keys list `
  --account-name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --query "[0].value" -o tsv

az storage share create `
  --name "botdata" `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --output table

az containerapp env storage set `
  --name $CONTAINER_APP_ENV `
  --resource-group $RESOURCE_GROUP `
  --storage-name "botdata" `
  --azure-file-account-name $STORAGE_ACCOUNT `
  --azure-file-account-key $STORAGE_KEY `
  --azure-file-share-name "botdata" `
  --access-mode ReadWrite `
  --output table

Write-Host "      Persistent storage ready." -ForegroundColor Green

# ── Step 8: Deploy Container App ──────────────────────────────────────────────
Write-Host "[8/9] Deploying bot to Azure Container Apps..." -ForegroundColor Yellow
az containerapp create `
  --name $CONTAINER_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --environment $CONTAINER_APP_ENV `
  --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" `
  --registry-server $ACR_LOGIN_SERVER `
  --registry-username $ACR_USERNAME `
  --registry-password $ACR_PASSWORD `
  --cpu 0.5 `
  --memory "1.0Gi" `
  --min-replicas 1 `
  --max-replicas 1 `
  --ingress disabled `
  --env-vars `
    "DISCORD_TOKEN=$DISCORD_TOKEN" `
    "GROQ_API_KEY=$GROQ_API_KEY" `
    "OWNER_IDS=$OWNER_IDS" `
  --output table

Write-Host "      Container App deployed." -ForegroundColor Green

# ── Step 9: Show status ────────────────────────────────────────────────────────
Write-Host "[9/9] Checking deployment status..." -ForegroundColor Yellow
az containerapp show `
  --name $CONTAINER_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --query "properties.runningStatus" -o tsv

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " SUCCESS! Bot is now LIVE on Azure!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host " View live logs with:" -ForegroundColor Cyan
Write-Host " az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow" -ForegroundColor White
Write-Host ""
