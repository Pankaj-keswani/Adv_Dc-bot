"""
json_handler.py — Persistent per-guild JSON config storage.
Each guild gets its own file: data/guilds/<guild_id>.json
"""

import json
import os
import asyncio
from pathlib import Path

GUILD_DATA_DIR = Path("data/guilds")
GUILD_DATA_DIR.mkdir(parents=True, exist_ok=True)

_lock = asyncio.Lock()

DEFAULT_GUILD_CONFIG = {
    "prefix": "!",
    "welcome_channel": None,
    "farewell_channel": None,
    "ai_channel": None,
    "log_channel": None,
    "mute_role": None,
    "auto_role": None,
    "ticket_category": None,
    "bad_words": [],
    "anti_spam": True,
    "link_filter": False,
    "reaction_roles": {},     # {message_id: {emoji: role_id}}
    "level_up_channel": None,
    "giveaways": {},
    "blacklisted_users": [],
    "disabled_commands": [],
}


def _guild_path(guild_id: int) -> Path:
    return GUILD_DATA_DIR / f"{guild_id}.json"


def get_guild_config(guild_id: int) -> dict:
    """Load guild config synchronously (safe for startup)."""
    path = _guild_path(guild_id)
    if not path.exists():
        _write_sync(path, DEFAULT_GUILD_CONFIG.copy())
        return DEFAULT_GUILD_CONFIG.copy()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # fill in any new keys added since last save
    updated = False
    for k, v in DEFAULT_GUILD_CONFIG.items():
        if k not in data:
            data[k] = v
            updated = True
    if updated:
        _write_sync(path, data)
    return data


def _write_sync(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def save_guild_config(guild_id: int, data: dict):
    """Async save guild config."""
    async with _lock:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write_sync, _guild_path(guild_id), data)


async def update_guild_key(guild_id: int, key: str, value):
    """Update a single key in the guild config."""
    cfg = get_guild_config(guild_id)
    cfg[key] = value
    await save_guild_config(guild_id, cfg)


def read_json(path: str) -> dict | list:
    """Generic JSON read."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data):
    """Generic JSON write."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
