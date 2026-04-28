"""
main.py — Entry point for the Advanced Discord Bot.
Handles bot initialization, cog loading, and on_ready event.
"""

import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
import colorlog
from pathlib import Path
from config.settings import DISCORD_TOKEN, DEFAULT_PREFIX, OWNER_IDS
from handlers.json_handler import get_guild_config

# ── Logging Setup ─────────────────────────────────────────────────────────────

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s[%(asctime)s] %(levelname)s%(reset)s — %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
))

logging.basicConfig(
    handlers=[
        handler,
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
    level=logging.INFO,
)

log = logging.getLogger("bot")

# Suppress noisy discord.py logs
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)

# ── Ensure data directories ───────────────────────────────────────────────────

Path("data").mkdir(exist_ok=True)
Path("data/guilds").mkdir(exist_ok=True)

# ── Dynamic prefix ────────────────────────────────────────────────────────────

async def get_prefix(bot: commands.Bot, message: discord.Message):
    if not message.guild:
        return DEFAULT_PREFIX
    cfg = get_guild_config(message.guild.id)
    return cfg.get("prefix", DEFAULT_PREFIX)

# ── Bot Intents ───────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.reactions = True
intents.voice_states = True

# ── Bot Class ─────────────────────────────────────────────────────────────────

class AdvancedBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            owner_ids=set(OWNER_IDS),
            help_command=CustomHelpCommand(),
            case_insensitive=True,
            strip_after_prefix=True,
        )

    async def setup_hook(self):
        """Load all cogs on startup."""
        cogs = [
            "cogs.chatbot",
            "cogs.music",
            "cogs.economy",
            "cogs.fun",
            "cogs.games",
            "cogs.info",
            "cogs.moderation",
            "cogs.owner",
            "cogs.extras",
            "cogs.permissions",
            "cogs.activity",
            "handlers.event_handler",
            "handlers.error_handler",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info("✅ Loaded: %s", cog)
            except Exception as e:
                log.error("❌ Failed to load %s: %s", cog, e)

    async def on_ready(self):
        log.info("=" * 50)
        log.info("🤖 Logged in as: %s (ID: %s)", self.user, self.user.id)
        log.info("📡 Connected to %d guild(s)", len(self.guilds))
        log.info("🐍 discord.py version: %s", discord.__version__)
        log.info("=" * 50)

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | !help"
            )
        )

        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            log.info("✅ Synced %d slash command(s) globally", len(synced))
        except Exception as e:
            log.error("❌ Failed to sync slash commands: %s", e)

    async def on_guild_join(self, guild: discord.Guild):
        log.info("➕ Joined guild: %s (ID: %s)", guild.name, guild.id)
        # Initialize guild config
        get_guild_config(guild.id)

    async def on_guild_remove(self, guild: discord.Guild):
        log.info("➖ Removed from guild: %s", guild.name)


# ── Custom Help Command ───────────────────────────────────────────────────────

# Colour per category for visual distinction
COG_COLOURS = {
    "Music":       0x1DB954,  # Spotify green
    "Economy":     0xF1C40F,  # Gold
    "Fun":         0xFF6B6B,  # Coral
    "Games":       0x9B59B6,  # Purple
    "Info":        0x3498DB,  # Blue
    "Moderation":  0xE74C3C,  # Red
    "Extras":      0x95A5A6,  # Grey
    "Permissions": 0xE67E22,  # Orange
}

class CustomHelpCommand(commands.HelpCommand):

    def _cog_colour(self, cog_name: str) -> int:
        return COG_COLOURS.get(cog_name, 0x7289DA)

    async def send_bot_help(self, mapping):
        """Overview — all categories."""
        embed = discord.Embed(
            title="🤖 Th3on.ai — Command Centre",
            description=(
                "Use `!help <category>` for a full list of commands in that category.\n"
                "Use `!help <command>` for details about a specific command.\n\n"
                "**Prefix:** `!`  |  Slash commands: type `/` in chat"
            ),
            color=0x7289DA,
        )

        for cog, cmds in mapping.items():
            visible = [c for c in cmds if not c.hidden]
            if not visible:
                continue
            cog_name = getattr(cog, "qualified_name", "Misc")
            # Show first 6 commands with a note if there are more
            names = [f"`{c.name}`" for c in visible[:6]]
            extra = f" *+{len(visible)-6} more*" if len(visible) > 6 else ""
            embed.add_field(
                name=f"{cog_name} ({len(visible)})",
                value=" ".join(names) + extra,
                inline=False
            )

        embed.set_footer(text="Tip: !help Music  →  shows all music commands")
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog):
        """Full list for one category."""
        visible = [c for c in cog.get_commands() if not c.hidden]
        cog_name = cog.qualified_name
        embed = discord.Embed(
            title=f"📂 {cog_name} Commands",
            description=cog.description or f"All `{cog_name}` commands are listed below.",
            color=self._cog_colour(cog_name),
        )
        for cmd in visible:
            usage = f"!{cmd.qualified_name}"
            if cmd.signature:
                usage += f" {cmd.signature}"
            aliases = (
                f" (aliases: {', '.join(f'`{a}`' for a in cmd.aliases)})"
                if cmd.aliases else ""
            )
            embed.add_field(
                name=f"`{usage}`{aliases}",
                value=cmd.short_doc or "No description.",
                inline=False
            )
        embed.set_footer(text="!help <command>  →  more details")
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        """Detailed help for one command."""
        cog_name = command.cog.qualified_name if command.cog else "Misc"
        embed = discord.Embed(
            title=f"📖 !{command.qualified_name}",
            description=command.help or command.short_doc or "No description available.",
            color=self._cog_colour(cog_name),
        )
        usage = f"!{command.qualified_name}"
        if command.signature:
            usage += f" {command.signature}"
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        if command.aliases:
            embed.add_field(
                name="Aliases",
                value=" | ".join(f"`!{a}`" for a in command.aliases),
                inline=False
            )
        embed.add_field(name="Category", value=cog_name, inline=True)
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error: str):
        embed = discord.Embed(
            title="❌ Command Not Found",
            description=f"{error}\n\nUse `!help` to see all commands.",
            color=0xE74C3C
        )
        await self.get_destination().send(embed=embed)


from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_webserver():
    """Starts a dummy web server on port 7860 for Hugging Face Spaces health checks."""
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 7860)
    await site.start()
    log.info("🌐 Health check server started on port 7860")

# ── Entry Point ───────────────────────────────────────────────────────────────

async def main():
    if not DISCORD_TOKEN:
        log.critical("❌ DISCORD_TOKEN not found! Make sure it is set in Hugging Face Secrets.")
        sys.exit(1)

    # Start health check server for Hugging Face compatibility
    await start_webserver()

    bot = AdvancedBot()
    
    # ── Connection Retry Logic ───────────────────────────────────────────────
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            log.info(f"🚀 Starting bot (Attempt {attempt}/{max_retries})...")
            async with bot:
                # Force IPv4 to avoid common Hugging Face connection errors
                import aiohttp
                connector = aiohttp.TCPConnector(family=aiohttp.socket.AF_INET)
                bot.http.connector = connector
                
                await bot.start(DISCORD_TOKEN)
                break # Success!
        except Exception as e:
            log.error(f"❌ Connection failed: {e}")
            if attempt < max_retries:
                log.info(f"⏳ Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2 # Exponential backoff
            else:
                log.critical("💀 All connection attempts failed. Shutting down.")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
