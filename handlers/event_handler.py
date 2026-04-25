"""
event_handler.py — Guild events: member join/leave, role changes, message logs.
"""

import discord
from discord.ext import commands
from config.settings import COLOR_SUCCESS, COLOR_ERROR, COLOR_INFO
from handlers.json_handler import get_guild_config
import logging

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
                embed = discord.Embed(
                    title=f"👋 Welcome to {guild.name}!",
                    description=(
                        f"Hey {member.mention}, welcome aboard!\n"
                        f"You are member **#{guild.member_count}**.\n"
                        f"Read the rules and enjoy your stay! 🎉"
                    ),
                    color=COLOR_SUCCESS,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"ID: {member.id}")
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

    # ── Reaction Roles ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        cfg = get_guild_config(payload.guild_id)
        rr = cfg.get("reaction_roles", {})
        msg_key = str(payload.message_id)
        if msg_key not in rr:
            return
        emoji_key = str(payload.emoji)
        if emoji_key not in rr[msg_key]:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(rr[msg_key][emoji_key]))
        if not role:
            return
        member = guild.get_member(payload.user_id)
        if member and not member.bot:
            try:
                await member.add_roles(role, reason="Reaction role")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        cfg = get_guild_config(payload.guild_id)
        rr = cfg.get("reaction_roles", {})
        msg_key = str(payload.message_id)
        if msg_key not in rr:
            return
        emoji_key = str(payload.emoji)
        if emoji_key not in rr[msg_key]:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(rr[msg_key][emoji_key]))
        if not role:
            return
        member = guild.get_member(payload.user_id)
        if member and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(EventHandler(bot))
