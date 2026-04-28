"""
event_handler.py — Guild events: member join/leave, role changes, message logs.
"""

import discord
from discord.ext import commands
from config.settings import COLOR_SUCCESS, COLOR_ERROR, COLOR_INFO
from handlers.json_handler import get_guild_config
from handlers.image_gen import generate_welcome_image
import logging
import io

log = logging.getLogger("bot")


class EventHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Member Join ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        cfg = get_guild_config(guild.id)

        # Auto-role assignment
        if cfg.get("auto_role"):
            role = guild.get_role(int(cfg["auto_role"]))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.Forbidden:
                    pass

        # Welcome message
        ch_id = cfg.get("welcome_channel")
        if ch_id:
            channel = guild.get_channel(int(ch_id))
            if channel:
                # Generate custom image
                try:
                    img_data = await generate_welcome_image(member)
                    file = discord.File(fp=img_data, filename=f"welcome_{member.id}.png")
                    
                    embed = discord.Embed(
                        title=f"👋 Welcome to {guild.name}!",
                        description=f"Hey {member.mention}, welcome aboard! You are our **{guild.member_count}th** member. 🎉",
                        color=COLOR_SUCCESS,
                    )
                    embed.set_image(url=f"attachment://welcome_{member.id}.png")
                    embed.set_footer(text=f"User ID: {member.id}")
                    
                    await channel.send(embed=embed, file=file)
                except Exception as e:
                    log.error(f"Failed to generate welcome image: {e}")
                    # Fallback to simple embed if image generation fails
                    embed = discord.Embed(
                        title=f"👋 Welcome to {guild.name}!",
                        description=f"Hey {member.mention}, welcome aboard! Read the rules and enjoy your stay! 🎉",
                        color=COLOR_SUCCESS,
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)

        log.info("Member joined: %s in %s", member, guild)

    # ── Member Leave ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        cfg = get_guild_config(guild.id)

        ch_id = cfg.get("farewell_channel")
        if ch_id:
            channel = guild.get_channel(int(ch_id))
            if channel:
                embed = discord.Embed(
                    title=f"👋 Goodbye, {member.display_name}",
                    description=f"**{member}** has left the server. We had **{guild.member_count}** members.",
                    color=COLOR_ERROR,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

        log.info("Member left: %s from %s", member, guild)

    # ── Member Update (role changes, nickname) ────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        cfg = get_guild_config(after.guild.id)
        log_ch_id = cfg.get("log_channel")
        if not log_ch_id:
            return
        channel = after.guild.get_channel(int(log_ch_id))
        if not channel:
            return

        # Nickname change
        if before.nick != after.nick:
            embed = discord.Embed(title="✏️ Nickname Changed", color=COLOR_INFO)
            embed.add_field(name="Member", value=after.mention, inline=False)
            embed.add_field(name="Before", value=before.nick or "None", inline=True)
            embed.add_field(name="After", value=after.nick or "None", inline=True)
            await channel.send(embed=embed)

        # Role changes
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        if added or removed:
            embed = discord.Embed(title="🎭 Roles Updated", color=COLOR_INFO)
            embed.add_field(name="Member", value=after.mention, inline=False)
            if added:
                embed.add_field(name="Added", value=" ".join(r.mention for r in added), inline=True)
            if removed:
                embed.add_field(name="Removed", value=" ".join(r.mention for r in removed), inline=True)
            await channel.send(embed=embed)

    # ── Guild Update ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        cfg = get_guild_config(after.id)
        log_ch_id = cfg.get("log_channel")
        if not log_ch_id:
            return
        channel = after.get_channel(int(log_ch_id))
        if not channel:
            return
        if before.name != after.name:
            embed = discord.Embed(title="🏠 Server Renamed", color=COLOR_INFO,
                                  description=f"`{before.name}` → `{after.name}`")
            await channel.send(embed=embed)

    # ── Message Deleted ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = get_guild_config(message.guild.id)
        log_ch_id = cfg.get("log_channel")
        if not log_ch_id:
            return
        channel = message.guild.get_channel(int(log_ch_id))
        if not channel or message.channel.id == int(log_ch_id):
            return
        embed = discord.Embed(title="🗑️ Message Deleted", color=COLOR_ERROR)
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content[:1024] or "*No text*", inline=False)
        await channel.send(embed=embed)

    # ── Message Edited ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        cfg = get_guild_config(before.guild.id)
        log_ch_id = cfg.get("log_channel")
        if not log_ch_id:
            return
        channel = before.guild.get_channel(int(log_ch_id))
        if not channel:
            return
        embed = discord.Embed(title="✏️ Message Edited", color=COLOR_INFO)
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:512] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:512] or "*empty*", inline=False)
        await channel.send(embed=embed)

    # ── Smart DM Help Listener ────────────────────────────────────────────────
    #
    # When a user messages the bot in DMs (or types !commands in a server),
    # the bot replies with the right help page automatically.
    #
    # Keyword categories understood naturally:
    #   "music", "economy", "mod"/"moderation", "fun", "games", "info",
    #   "perm"/"permission", "all"/"help"
    #
    # If the user's message matches a specific command name (e.g. "skip"),
    # the bot shows detailed help for that command.

    # Map of keywords → cog qualified names
    CATEGORY_KEYWORDS = {
        "music":       ["music", "song", "play", "audio", "queue", "volume", "skip", "np", "nowplaying"],
        "economy":     ["economy", "coin", "coins", "balance", "money", "bank", "shop"],
        "moderation":  ["mod", "moderation", "ban", "kick", "mute", "warn", "clear", "purge"],
        "fun":         ["fun", "meme", "joke", "random"],
        "games":       ["game", "games", "trivia", "guess"],
        "info":        ["info", "server", "user", "avatar", "ping"],
        "extras":      ["extra", "extras", "misc", "other"],
        "permissions": ["perm", "perms", "permission", "permissions", "access", "restrict"],
    }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and messages that are commands (prefix-handled elsewhere)
        if message.author.bot:
            return

        # ── Only handle DMs or explicit !commands trigger in servers ──
        is_dm = isinstance(message.channel, discord.DMChannel)
        content = message.content.strip().lower()

        # In server: only respond if someone types `!commands`
        if not is_dm:
            if content in ("!commands", "!command"):
                await self.bot.get_command("help").invoke(
                    await self.bot.get_context(message)
                )
            return

        # ── DM handling below ──
        # Strip exclamation prefix if user typed a command
        if content.startswith("!"):
            return  # Let the normal command processor handle it

        # Ignore empty messages
        if not content:
            return

        # 1) Check if it matches a command name directly  e.g. "skip" / "what is skip"
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            if cmd.name in content or any(a in content for a in cmd.aliases):
                ctx = await self.bot.get_context(message)
                ctx.command = self.bot.get_command("help")
                embed = discord.Embed(
                    title=f"📖 !{cmd.qualified_name}",
                    description=cmd.help or cmd.short_doc or "No description available.",
                    color=0x7289DA,
                )
                usage = f"!{cmd.qualified_name}"
                if cmd.signature:
                    usage += f" {cmd.signature}"
                embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
                if cmd.aliases:
                    embed.add_field(
                        name="Aliases",
                        value=" | ".join(f"`!{a}`" for a in cmd.aliases),
                        inline=False,
                    )
                if cmd.cog:
                    embed.add_field(name="Category", value=cmd.cog.qualified_name, inline=True)
                await message.channel.send(embed=embed)
                return

        # 2) Check if it matches a category keyword  e.g. "music commands" / "show me music"
        for cog_name, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                cog = discord.utils.find(
                    lambda c: c.qualified_name.lower() == cog_name,
                    self.bot.cogs.values()
                )
                if cog:
                    ctx = await self.bot.get_context(message)
                    await self.bot.help_command.send_cog_help(cog)
                    return

        # 3) General "help" / "all commands" / "what can you do"
        if any(kw in content for kw in ("help", "all", "command", "what can", "what do")):
            ctx = await self.bot.get_context(message)
            await self.bot.help_command.send_bot_help(
                {c: list(c.get_commands()) for c in self.bot.cogs.values()}
            )
            return

        # 4) Fallback greeting / unknown message
        await message.channel.send(
            "👋 Hey! Type `!help` to see all my commands, or ask me something like:\n"
            "• `music commands`\n"
            "• `what is skip`\n"
            "• `economy commands`"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHandler(bot))
