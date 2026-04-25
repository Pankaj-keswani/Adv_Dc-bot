"""
deploy_to_azure.py — Reliable Azure deployment using Python subprocess.
Reads secrets from .env and deploys the Discord bot to Azure Container Apps.
"""

import subprocess
import sys
import os
import random
import string
from dotenv import load_dotenv

# Full path to az CLI on Windows (avoids PATH lookup issues in subprocess)
AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
RG            = "discord-bot-rg"
LOCATION      = "centralindia"
RAND          = "6798"
ACR_NAME      = f"discordbotacr{RAND}"
STORAGE_NAME  = f"botstore{RAND}"
APP_ENV       = "discord-bot-env"
APP_NAME      = "advanced-discord-bot"
IMAGE         = "discord-bot:latest"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "").strip()
OWNER_IDS     = os.getenv("OWNER_IDS", "").strip()

def run(args, check=True, capture=False):
    """Run an az CLI command and return output."""
    cmd = [AZ] + list(args)
    print(f"  $ az {' '.join(args)}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if check and result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, encoding='utf-8', errors='replace')
        if check and result.returncode != 0:
            print(f"  ERROR: command failed (exit {result.returncode})")
            sys.exit(1)
        return None

def header(step, total, msg):
    print(f"\n[{step}/{total}] {msg}")
    print("─" * 60)

def main():

    print("\n" + "="*60)
    print("  Advanced Discord Bot - Azure Deployment")
    print("="*60)
    print(f"  Region      : {LOCATION}")
    print(f"  ACR Name    : {ACR_NAME}")
    print(f"  Storage     : {STORAGE_NAME}")
    print(f"  App Name    : {APP_NAME}")
    print("="*60)

    # ── 1. Register providers ──────────────────────────────────────────────────
    # header(1, 8, "Registering Azure providers...")
    # for ns in ["Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry", "Microsoft.Storage"]:
    #     run(["provider", "register", "--namespace", ns])
    # print("  [OK] Providers registered.")

    # ── 2. Create Resource Group ───────────────────────────────────────────────
    # header(2, 8, f"Creating Resource Group '{RG}'...")
    # run(["group", "create", "--name", RG, "--location", LOCATION])
    # print("  [OK] Resource Group created.")

    # ── 3. Create Container Registry ──────────────────────────────────────────
    # header(3, 8, f"Creating Container Registry '{ACR_NAME}'...")
    # run(["acr", "create",
    #      "--resource-group", RG,
    #      "--name", ACR_NAME,
    #      "--sku", "Basic",
    #      "--admin-enabled", "true"])
    # print("  [OK] Container Registry created.")

    # ── 4. Build & push image via ACR ─────────────────────────────────────────
    # We already built and pushed the image locally using Docker Desktop!
    # header(4, 8, "Building Docker image with FFmpeg and pushing to ACR...")
    # print("  This takes 3-5 minutes - please wait...")
    # run(["acr", "build",
    #      "--registry", ACR_NAME,
    #      "--image", IMAGE,
    #      "--platform", "linux/amd64",
    #      "."])
    # print("  [OK] Image built and pushed!")

    # ── 5. Get ACR credentials ─────────────────────────────────────────────────
    header(5, 8, "Getting registry credentials...")
    acr_server   = run(["acr", "show", "--name", ACR_NAME, "--query", "loginServer", "-o", "tsv"], capture=True)
    acr_user     = run(["acr", "credential", "show", "--name", ACR_NAME, "--query", "username", "-o", "tsv"], capture=True)
    acr_password = run(["acr", "credential", "show", "--name", ACR_NAME, "--query", "passwords[0].value", "-o", "tsv"], capture=True)
    print(f"  [OK] Registry: {acr_server}")

    # ── 6. Create Container Apps Environment ──────────────────────────────────
    header(6, 8, "Creating Container Apps Environment...")
    run(["containerapp", "env", "create",
         "--name", APP_ENV,
         "--resource-group", RG,
         "--location", LOCATION])
    print("  [OK] Environment created.")

    # ── 7. Create Storage for persistent data ─────────────────────────────────
    header(7, 8, "Creating Azure Storage for bot data...")
    run(["storage", "account", "create",
         "--name", STORAGE_NAME,
         "--resource-group", RG,
         "--location", LOCATION,
         "--sku", "Standard_LRS"])

    storage_key = run(["storage", "account", "keys", "list",
                       "--account-name", STORAGE_NAME,
                       "--resource-group", RG,
                       "--query", "[0].value", "-o", "tsv"], capture=True)

    run(["storage", "share", "create",
         "--name", "botdata",
         "--account-name", STORAGE_NAME,
         "--account-key", storage_key])

    run(["containerapp", "env", "storage", "set",
         "--name", APP_ENV,
         "--resource-group", RG,
         "--storage-name", "botdata",
         "--azure-file-account-name", STORAGE_NAME,
         "--azure-file-account-key", storage_key,
         "--azure-file-share-name", "botdata",
         "--access-mode", "ReadWrite"])
    print("  [OK] Persistent storage ready.")

    # ── 8. Deploy Container App ────────────────────────────────────────────────
    header(8, 8, "Deploying Discord Bot to Azure Container Apps...")
    run(["containerapp", "create",
         "--name", APP_NAME,
         "--resource-group", RG,
         "--environment", APP_ENV,
         "--image", f"{acr_server}/{IMAGE}",
         "--registry-server", acr_server,
         "--registry-username", acr_user,
         "--registry-password", acr_password,
         "--cpu", "0.5",
         "--memory", "1.0Gi",
         "--min-replicas", "1",
         "--max-replicas", "1",
         "--ingress", "disabled",
         "--env-vars",
             f"DISCORD_TOKEN={DISCORD_TOKEN}",
             f"GROQ_API_KEY={GROQ_API_KEY}",
             f"OWNER_IDS={OWNER_IDS}"])
    print("  [OK] Container App deployed!")

    print("\n" + "="*60)
    print("  SUCCESS! Your bot is now LIVE on Azure!")
    print("="*60)
    print(f"\n  To view live logs, run:")
    print(f"  az containerapp logs show --name {APP_NAME} --resource-group {RG} --follow")
    print()

if __name__ == "__main__":
    main()
