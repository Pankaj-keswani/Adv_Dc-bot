"""
info.py — Server, user, and bot information commands.
"""

import discord
from discord.ext import commands
from discord import app_commands
import platform
import psutil
import time
from datetime import datetime
from config.settings import COLOR_INFO, COLOR_PRIMARY, COLOR_SUCCESS
import logging

log = logging.getLogger("bot")

START_TIME = time.time()


class Info(commands.Cog):
    """ℹ️ Information commands for server, users, and the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !serverinfo ───────────────────────────────────────────────────────────

    @commands.command(name="serverinfo", aliases=["si", "guildinfo"])
    async def serverinfo(self, ctx: commands.Context):
        """Display information about this server."""
        guild = ctx.guild
        embed = discord.Embed(title=f"🏠 {guild.name}", color=COLOR_INFO)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        text_ch = len(guild.text_channels)
        voice_ch = len(guild.voice_channels)

        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="🌍 Region", value=str(guild.preferred_locale), inline=True)
        embed.add_field(name="👥 Members", value=f"👤 {humans} humans | 🤖 {bots} bots", inline=True)
        embed.add_field(name="💬 Channels", value=f"📝 {text_ch} text | 🔊 {voice_ch} voice", inline=True)
        embed.add_field(name="🎭 Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="🆔 Server ID", value=str(guild.id), inline=True)
        embed.add_field(name="🔒 Verification", value=str(guild.verification_level).title(), inline=True)
        embed.add_field(name="💎 Boosts", value=f"Level {guild.premium_tier} — {guild.premium_subscription_count} boosts", inline=True)

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        await ctx.send(embed=embed)

    # ── !userinfo ─────────────────────────────────────────────────────────────

    @commands.command(name="userinfo", aliases=["ui", "whois"])
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        """Display information about a user."""
        member = member or ctx.author
        embed = discord.Embed(title=f"👤 {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)

        roles = [r.mention for r in member.roles if r != ctx.guild.default_role]

        embed.add_field(name="🆔 User ID", value=str(member.id), inline=True)
        embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="📛 Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="📅 Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="📥 Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="🎭 Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(
            name=f"🎭 Roles ({len(roles)})",
            value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else "") if roles else "None",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ── !botinfo ──────────────────────────────────────────────────────────────

    @commands.command(name="botinfo", aliases=["bi", "about"])
    async def botinfo(self, ctx: commands.Context):
        """Display information about the bot."""
        uptime_sec = int(time.time() - START_TIME)
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h}h {m}m {s}s"

        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / 1024 / 1024
        cpu = psutil.cpu_percent(interval=0.1)

        embed = discord.Embed(
            title=f"🤖 {self.bot.user.name}",
            description="An advanced Discord bot with AI, music, economy & more!",
            color=COLOR_PRIMARY,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
        embed.add_field(name="📡 Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="🏠 Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👥 Users", value=str(sum(g.member_count for g in self.bot.guilds)), inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📦 discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="💾 Memory", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="🖥️ CPU", value=f"{cpu}%", inline=True)
        embed.add_field(name="⚙️ Commands", value=str(len(self.bot.commands)), inline=True)
        await ctx.send(embed=embed)

    # ── !ping ─────────────────────────────────────────────────────────────────

    @commands.command(name="ping", aliases=["latency"])
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        color = COLOR_SUCCESS if latency < 100 else (COLOR_INFO if latency < 200 else 0xE74C3C)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**{latency}ms** latency",
            color=color,
        )
        await ctx.send(embed=embed)

    # ── !uptime ───────────────────────────────────────────────────────────────

    @commands.command(name="uptime", aliases=["up"])
    async def uptime(self, ctx: commands.Context):
        """Show how long the bot has been running."""
        uptime_sec = int(time.time() - START_TIME)
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(f"⏱️ Bot has been running for **{h}h {m}m {s}s**")

    # ── !membercount ──────────────────────────────────────────────────────────

    @commands.command(name="membercount", aliases=["mc", "members"])
    async def membercount(self, ctx: commands.Context):
        """Show the member count."""
        guild = ctx.guild
        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        embed = discord.Embed(title=f"👥 {guild.name} Members", color=COLOR_INFO)
        embed.add_field(name="Total", value=str(guild.member_count), inline=True)
        embed.add_field(name="👤 Humans", value=str(humans), inline=True)
        embed.add_field(name="🤖 Bots", value=str(bots), inline=True)
        await ctx.send(embed=embed)

    # ── !roleinfo ─────────────────────────────────────────────────────────────

    @commands.command(name="roleinfo", aliases=["ri"])
    async def roleinfo(self, ctx: commands.Context, *, role: discord.Role):
        """Get information about a role."""
        perms = [p.replace("_", " ").title() for p, v in role.permissions if v]
        embed = discord.Embed(title=f"🎭 Role: {role.name}", color=role.color)
        embed.add_field(name="🆔 ID", value=str(role.id), inline=True)
        embed.add_field(name="🎨 Color", value=str(role.color), inline=True)
        embed.add_field(name="📌 Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="🤖 Managed", value="Yes" if role.managed else "No", inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="👥 Members", value=str(len(role.members)), inline=True)
        embed.add_field(
            name=f"🔑 Permissions ({len(perms)})",
            value=", ".join(perms[:8]) + ("..." if len(perms) > 8 else "") if perms else "None",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ── !inviteinfo / !banner ─────────────────────────────────────────────────

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, member: discord.Member = None):
        """View a member's profile banner."""
        target = member or ctx.author
        user = await self.bot.fetch_user(target.id)
        if not user.banner:
            return await ctx.send(f"❌ {target.display_name} has no banner.")
        embed = discord.Embed(title=f"{target.display_name}'s Banner", color=COLOR_PRIMARY)
        embed.set_image(url=user.banner.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
