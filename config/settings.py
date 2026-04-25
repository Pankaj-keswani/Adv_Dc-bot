import os
from dotenv import load_dotenv

load_dotenv()

# ── Core Bot Settings ─────────────────────────────────────────────────────────
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")

# ── Prefix ────────────────────────────────────────────────────────────────────
DEFAULT_PREFIX  = "!"

# ── Owner IDs (put your Discord user ID here) ─────────────────────────────────
OWNER_IDS       = [int(x) for x in os.getenv("OWNER_IDS", "0").split(",") if x.strip().isdigit()]

# ── Groq AI Model ─────────────────────────────────────────────────────────────
GROQ_MODEL      = "llama-3.3-70b-versatile"
AI_MAX_TOKENS   = 1024
AI_MEMORY_LIMIT = 20           # messages kept per user in memory

# ── Economy ───────────────────────────────────────────────────────────────────
CURRENCY_NAME   = "Coins"
CURRENCY_EMOJI  = "🪙"
DAILY_AMOUNT    = 250
WORK_MIN        = 50
WORK_MAX        = 300
GAMBLE_MIN_BET  = 10

# ── Music ─────────────────────────────────────────────────────────────────────
MAX_QUEUE_SIZE  = 200
DEFAULT_VOLUME  = 50

# ── Leveling ──────────────────────────────────────────────────────────────────
XP_PER_MESSAGE  = (15, 40)     # random range per message
XP_COOLDOWN     = 60           # seconds between XP awards per user

# ── Moderation ────────────────────────────────────────────────────────────────
MUTE_ROLE_NAME  = "Muted"

# ── Colors (hex) ──────────────────────────────────────────────────────────────
COLOR_PRIMARY   = 0x7289DA
COLOR_SUCCESS   = 0x2ECC71
COLOR_ERROR     = 0xE74C3C
COLOR_WARNING   = 0xF39C12
COLOR_INFO      = 0x3498DB
COLOR_ECONOMY   = 0xF1C40F
COLOR_MUSIC     = 0x9B59B6

# ── Bot System Prompt ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are an advanced, friendly, and witty Discord bot assistant. "
    "You have a helpful, energetic personality. Keep responses concise but informative. "
    "You can use Discord markdown (bold, italic, code blocks). "
    "Never reveal that you are an AI language model — you are just the bot."
)
