#!/bin/bash
# ============================================================
# azure-deploy.sh — Deploy the Discord Bot to Azure Container Apps
# ============================================================
# Prerequisites:
#   - Azure CLI installed: https://learn.microsoft.com/cli/azure/install-azure-cli
#   - Docker Desktop installed and running
#   - Run: az login
# ============================================================

set -e

# ── CONFIGURATION (edit these) ───────────────────────────────────────────────
RESOURCE_GROUP="discord-bot-rg"
LOCATION="eastus"
ACR_NAME="advdiscordbotacr"          # Must be globally unique, lowercase only
CONTAINER_APP_NAME="advanced-discord-bot"
CONTAINER_APP_ENV="discord-bot-env"
IMAGE_NAME="advanced-discord-bot"
IMAGE_TAG="latest"

# Load secrets from .env
DISCORD_TOKEN=$(grep DISCORD_TOKEN .env | cut -d '=' -f2 | tr -d ' ')
GROQ_API_KEY=$(grep GROQ_API_KEY .env | cut -d '=' -f2 | tr -d ' ')

echo "============================================================"
echo "  Advanced Discord Bot — Azure Deployment"
echo "============================================================"

# ── Step 1: Create Resource Group ────────────────────────────────────────────
echo "[1/8] Creating Resource Group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table

# ── Step 2: Create Azure Container Registry ───────────────────────────────────
echo "[2/8] Creating Azure Container Registry..."
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output table

# ── Step 3: Get ACR credentials ───────────────────────────────────────────────
echo "[3/8] Retrieving ACR credentials..."
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ── Step 4: Build and push Docker image ───────────────────────────────────────
echo "[4/8] Building and pushing Docker image to ACR..."
az acr build \
  --registry "$ACR_NAME" \
  --image "$IMAGE_NAME:$IMAGE_TAG" \
  .

# ── Step 5: Create Container Apps Environment ─────────────────────────────────
echo "[5/8] Creating Container Apps Environment..."
az containerapp env create \
  --name "$CONTAINER_APP_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table

# ── Step 6: Create Azure File Share for persistent data ───────────────────────
STORAGE_ACCOUNT="${ACR_NAME}storage"
echo "[6/8] Creating Azure Storage for persistent bot data..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --output table

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" -o tsv)

az storage share create \
  --name "botdata" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --output table

# ── Step 7: Link storage to Container Apps env ────────────────────────────────
echo "[7/8] Linking persistent storage to Container Apps..."
az containerapp env storage set \
  --name "$CONTAINER_APP_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-name "botdata" \
  --azure-file-account-name "$STORAGE_ACCOUNT" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "botdata" \
  --access-mode ReadWrite \
  --output table

# ── Step 8: Create and deploy the Container App ───────────────────────────────
echo "[8/8] Deploying Container App..."
az containerapp create \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINER_APP_ENV" \
  --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --ingress disabled \
  --env-vars \
    "DISCORD_TOKEN=$DISCORD_TOKEN" \
    "GROQ_API_KEY=$GROQ_API_KEY" \
  --volume-mount "botdata:/app/data" \
  --output table

echo ""
echo "============================================================"
echo " ✅ Deployment Complete!"
echo " Bot is now running live on Azure Container Apps."
echo " Use: az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo "============================================================"
