# 🤖 Advanced Discord Bot

A **production-grade** Discord bot built in Python with AI chatbot, music, economy, moderation, games, and more — ready for **Microsoft Azure** deployment.

---

## ✨ Features

| Category | Commands |
|---|---|
| 🤖 **AI Chatbot** | `/chat`, `/forget`, `/setaichannel`, `!chat`, `!ask` |
| 🎵 **Music** | `!play`, `!skip`, `!stop`, `!queue`, `!volume`, `!playlist`, `!shuffle`, `!loop`, `!nowplaying` |
| 💰 **Economy** | `!balance`, `!daily`, `!work`, `!gamble`, `!pay`, `!leaderboard`, `!deposit`, `!withdraw`, `!shop` |
| 😄 **Fun** | `!8ball`, `!joke`, `!roast`, `!coinflip`, `!dice`, `!meme`, `!trivia`, `/poll`, `!quote` |
| 🎮 **Games** | `!tictactoe`, `!rps`, `!guess`, `!hangman`, `!slots` |
| ℹ️ **Info** | `!serverinfo`, `!userinfo`, `!botinfo`, `!ping`, `!uptime`, `!membercount`, `!roleinfo` |
| 🛡️ **Moderation** | `!ban`, `!kick`, `!mute`, `!unmute`, `!timeout`, `!warn`, `!warnings`, `!purge`, `!slowmode`, `!lock`, `!unlock` |
| 👑 **Owner** | `!eval`, `!reload`, `!shutdown`, `!announce`, `!blacklist`, `!sync`, `!setstatus` |
| ⚡ **Extras** | Leveling, Giveaways (`/giveaway`), Reminders (`/remind`), Tickets (`/ticket`), Auto-mod |

---

## 📁 Project Structure

```
Adv Dc Bot/
├── main.py                 # Bot entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image
├── docker-compose.yml      # Local Docker testing
├── azure-deploy.sh         # Azure deployment script
├── .env                    # Your tokens (never commit!)
├── config/
│   └── settings.py         # All configuration constants
├── cogs/                   # Feature modules
│   ├── chatbot.py          # AI chatbot (Groq/LLaMA)
│   ├── music.py            # Music player (yt-dlp)
│   ├── economy.py          # Economy system
│   ├── fun.py              # Fun commands
│   ├── games.py            # Games
│   ├── info.py             # Info commands
│   ├── moderation.py       # Moderation
│   ├── owner.py            # Owner-only commands
│   └── extras.py           # Leveling, giveaways, reminders, tickets
├── handlers/
│   ├── event_handler.py    # Guild events + reaction roles
│   ├── json_handler.py     # Per-guild JSON config
│   └── error_handler.py    # Global error handling
└── data/                   # Auto-created at runtime
    ├── economy.db          # SQLite database
    ├── guilds/             # Per-guild JSON configs
    └── bot.log             # Log file
```

---

## 🚀 Quick Start (Local)

### 1. Install Python 3.11+
Download from [python.org](https://www.python.org/downloads/)

### 2. Install FFmpeg (Required for Music)
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Linux/Mac**: `sudo apt install ffmpeg` / `brew install ffmpeg`

### 3. Set up your .env
```env
DISCORD_TOKEN = your_discord_token_here
GROQ_API_KEY  = your_groq_api_key_here
OWNER_IDS     = your_discord_user_id_here
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the bot
```bash
python main.py
```

---

## 🐳 Run with Docker (Recommended for Azure)

```bash
# Build and run locally
docker-compose up --build

# Run in background
docker-compose up -d --build
```

---

## ☁️ Deploy to Azure

> **Prerequisites:** Azure CLI installed + `az login` done + Docker running

```bash
# On Linux/Mac:
bash azure-deploy.sh

# On Windows (Git Bash or WSL):
bash azure-deploy.sh
```

### What the script does:
1. Creates an **Azure Resource Group**
2. Creates an **Azure Container Registry (ACR)** and pushes the Docker image
3. Creates an **Azure Container Apps Environment** (serverless, always-on)
4. Creates an **Azure File Share** for persistent SQLite + guild data
5. Deploys the bot with env variables set as secrets

### View live logs after deployment:
```bash
az containerapp logs show \
  --name advanced-discord-bot \
  --resource-group discord-bot-rg \
  --follow
```

---

## ⚙️ Important Bot Setup Commands

After inviting the bot to your server, run these as an admin:

| Command | Effect |
|---|---|
| `!setwelcome #channel` | Set welcome messages channel |
| `!setfarewell #channel` | Set goodbye messages channel |
| `!setlog #channel` | Set moderation log channel |
| `!setprefix <prefix>` | Change the command prefix |
| `/setaichannel #channel` | Set the AI auto-chat channel |
| `!sync` | Sync slash commands (owner only) |

---

## 🔗 Invite the Bot

Use Discord Developer Portal to generate an invite link with these permissions:
- `bot` scope with: Administrator (or individual permissions)
- `applications.commands` scope for slash commands

---

## 📌 .env Variables Reference

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your bot token from Discord Developer Portal |
| `GROQ_API_KEY` | Groq API key from [console.groq.com](https://console.groq.com) |
| `OWNER_IDS` | Your Discord user ID (comma-separated for multiple) |


<!-- Trigger Actions -->
