"""
deploy_to_vm.py — Automates deploying the Discord bot to an Azure Free Linux VM (B1s).
"""

import subprocess
import sys
import os
import random
import string
import json
import tarfile

# Full path to az CLI on Windows
AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

BASE_RG    = "discord-bot-vm"
LOCATIONS  = ["westus2", "southcentralus", "australiaeast", "japaneast", "northeurope", "uksouth", "canadacentral", "eastus2", "westus3", "koreacentral"]
VM_NAME    = "DiscordBotVM"
IMAGE      = "Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest"
SIZE       = "Standard_B1s"
USER       = "azureuser"

def run(args, capture=False):
    """Run a local command safely."""
    print(f"  $ {' '.join(args)}")
    cmd = args
    if cmd[0] == "az":
        cmd[0] = AZ
    
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            print(f"  ERROR: command failed (exit {result.returncode})")
            sys.exit(1)
        return None

def header(step, total, msg):
    print(f"\n[{step}/{total}] {msg}")
    print("─" * 60)

def create_archive():
    print("  Packaging bot source code...")
    archive_name = "bot.tar.gz"
    with tarfile.open(archive_name, "w:gz") as tar:
        for item in os.listdir("."):
            if item in ["venv", ".venv", "env", "__pycache__", ".git", ".idea", ".vscode", archive_name]:
                continue
            tar.add(item)
    print("  Done creating bot.tar.gz")
    return archive_name

def create_ssh_key():
    key_path = "bot_key"
    if not os.path.exists(key_path):
        print("  Generating dedicated SSH key for VM...")
        run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", key_path, "-N", ""])
    return key_path

def main():
    print("\n" + "="*60)
    print("  🚀 Advanced Discord Bot — Azure VM Deployment")
    print("="*60)
    print(f"  Target  : Best Available Region Loop")
    print(f"  VM Size : {SIZE} (100% Free Tier Supported)")
    print("="*60)

    # 1. Package code
    header(1, 6, "Creating deployment package...")
    archive = create_archive()
    
    # 2. SSH Keys
    header(2, 6, "Generating dedicated SSH key...")
    ssh_key = create_ssh_key()
    pub_key = f"{ssh_key}.pub"

    public_ip = None
    successful_loc = None
    successful_rg = None

    header(3, 6, "Finding available capacity for Free VM (auto-fallback)...")
    
    for loc in LOCATIONS:
        rg = f"{BASE_RG}-{loc}"
        print(f"\n  [-->] Trying region: {loc}")
        print(f"  Creating Resource Group '{rg}'...")
        run(["az", "group", "create", "--name", rg, "--location", loc])
        
        print(f"  Attempting to create Linux VM '{VM_NAME}' (takes ~2 mins)...")
        # Do not abort heavily on fail, just capture or let it fail gracefully
        cmd = ["az", "vm", "create", 
             "--resource-group", rg, 
             "--name", VM_NAME, 
             "--image", IMAGE, 
             "--admin-username", USER, 
             "--ssh-key-values", pub_key, 
             "--size", SIZE,
             "--public-ip-sku", "Standard"]
        
        # We run it manually and check returncode because run() exists on 1
        res = subprocess.run([AZ] + cmd[1:], encoding='utf-8', errors='replace')
        
        if res.returncode == 0:
            print(f"  SUCCESS! Azure allocated capacity in {loc}!")
            successful_loc = loc
            successful_rg = rg
            break
        else:
            print(f"  [X] Failed in {loc} (Likely out of free capacity). Moving to next region...")
            # Optionally delete the empty RG in background:
            # subprocess.Popen(["az", "group", "delete", "--name", rg, "--yes", "--no-wait"], shell=True)

    if not successful_rg:
        print("\n  ❌ ERROR: Exhausted all fallback regions. Azure currently has no Standard_B1s capacity available for Free Tier across all tested regions globally.")
        sys.exit(1)

    print("  Fetching Public IP Address...")
    public_ip = run(["az", "vm", "show", 
                     "--show-details", 
                     "--resource-group", successful_rg, 
                     "--name", VM_NAME, 
                     "--query", "publicIps", 
                     "--output", "tsv"], capture=True)
    
    if not public_ip:
        print("  Could not retrieve Public IP. Check Azure Portal.")
        sys.exit(1)

    print(f"  ✅ VM created! Public IP: {public_ip}")

    # 5. Copy Code
    header(5, 6, "Copying code to the VM using SCP...")
    # StrictHostKeyChecking=accept-new adds the key automatically without prompting
    ssh_opts = ["-i", ssh_key, "-o", "StrictHostKeyChecking=accept-new"]
    run(["scp"] + ssh_opts + [archive, f"{USER}@{public_ip}:~/{archive}"])

    # 6. Remote Execution
    header(6, 6, "Installing Python, FFmpeg, and starting the bot (takes 3-5 mins)...")
    cmds = f"rm -rf bot && mkdir bot && tar -xzf {archive} -C bot && cd bot && bash vm_setup.sh"
    run(["ssh"] + ssh_opts + [f"{USER}@{public_ip}", cmds])

    print("\n" + "="*60)
    print("  🎉 SUCCESS! Your bot is LIVE and running on Azure VM!")
    print("="*60)
    print(f"  IP Address : {public_ip}")
    print(f"  SSH Command: ssh -i {ssh_key} {USER}@{public_ip}")
    print("="*60)
    print("\n  The bot is running as a background service.")
    print("  If the server restarts, the bot starts automatically!")

if __name__ == "__main__":
    main()
