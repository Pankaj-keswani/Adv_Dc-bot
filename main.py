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

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📖 Advanced Bot Help",
            description=(
                "Use `!help <command>` for details on a specific command.\n"
                "Slash commands are also available — type `/` to browse them.\n\n"
                "**Prefix:** `!` (customizable with `!setprefix`)"
            ),
            color=0x7289DA,
        )
        for cog, cmds in mapping.items():
            visible = [c for c in cmds if not c.hidden]
            if not visible:
                continue
            cog_name = getattr(cog, "qualified_name", "Misc")
            cmd_list = " ".join(f"`{c.name}`" for c in visible)
            embed.add_field(name=cog_name, value=cmd_list or "*No commands*", inline=False)

        embed.set_footer(text="[ ] = optional  < > = required | !help <command> for details")
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command: commands.Command):
        embed = discord.Embed(
            title=f"📖 !{command.qualified_name}",
            description=command.help or "No description.",
            color=0x7289DA,
        )
        if command.aliases:
            embed.add_field(name="Aliases", value=" | ".join(f"`{a}`" for a in command.aliases), inline=False)
        embed.add_field(
            name="Usage",
            value=f"`!{command.qualified_name} {command.signature}`" if command.signature else f"`!{command.qualified_name}`",
            inline=False,
        )
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog):
        visible = [c for c in cog.get_commands() if not c.hidden]
        embed = discord.Embed(
            title=f"📖 {cog.qualified_name} Commands",
            description=cog.description or "",
            color=0x7289DA,
        )
        for cmd in visible:
            embed.add_field(name=f"!{cmd.qualified_name}", value=cmd.short_doc or "No description", inline=False)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_error_message(self, error: str):
        embed = discord.Embed(title="❌ Help Error", description=error, color=0xE74C3C)
        channel = self.get_destination()
        await channel.send(embed=embed)


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
        log.critical("❌ DISCORD_TOKEN not found in .env file!")
        sys.exit(1)

    # Start health check server for Hugging Face compatibility
    await start_webserver()

    bot = AdvancedBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
