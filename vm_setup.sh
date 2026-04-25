#!/bin/bash
# vm_setup.sh — Runs on the Azure Linux VM to setup and start the bot

echo "========================================================"
echo " Starting Server Setup (Installing dependencies...)"
echo "========================================================"

# Stop the service if it exists during re-deploy
sudo systemctl stop discord-bot 2>/dev/null

# System updates and dependencies (FFmpeg for music)
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3.11 python3.11-venv python3-pip ffmpeg libopus-dev libffi-dev libnacl-dev dnsutils

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install bot requirements
pip install wheel
pip install -r requirements.txt

# Create the data/guilds directory
mkdir -p data/guilds

echo "========================================================"
echo " Setting up Systemd Service for 24/7 Uptime"
echo "========================================================"

# Create systemd service file
cat <<EOF | sudo tee /etc/systemd/system/discord-bot.service
[Unit]
Description=Advanced Discord Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start bot
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

echo "========================================================"
echo " Setup Complete! Bot is now running 24/7."
echo " Checking status:"
sudo systemctl status discord-bot --no-pager
echo "========================================================"
