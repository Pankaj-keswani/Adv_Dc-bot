"""
moderation.py — Full moderation suite: ban, kick, mute, warn, purge, slowmode, lock, etc.
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
from datetime import timedelta
from config.settings import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, MUTE_ROLE_NAME, OWNER_IDS
import logging

log = logging.getLogger("bot")
DB_PATH = "data/economy.db"

# ── Protected Users ───────────────────────────────────────────────────────────
# No moderation command can ever target these user IDs.
# OWNER_IDS are always included automatically.
# Add extra user IDs to EXTRA_PROTECTED if needed.
EXTRA_PROTECTED: list[int] = []   # e.g. [123456789, 987654321]
PROTECTED_IDS: set[int] = set(OWNER_IDS) | set(EXTRA_PROTECTED)


def is_protected(member: discord.Member) -> bool:
    """Returns True if this member is on the protected list."""
    return member.id in PROTECTED_IDS



async def _init_mod_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


def mod_check():
    """Require Manage Messages or higher."""
    async def predicate(ctx: commands.Context):
        return ctx.author.guild_permissions.manage_messages
    return commands.check(predicate)


class Moderation(commands.Cog):
    """🛡️ Moderation tools to keep your server safe."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await _init_mod_db()

    async def _get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
        if not role:
            role = await guild.create_role(
                name=MUTE_ROLE_NAME,
                permissions=discord.Permissions(send_messages=False, speak=False),
                reason="Auto-created Muted role",
            )
            for channel in guild.channels:
                try:
                    await channel.set_permissions(role, send_messages=False, speak=False)
                except discord.Forbidden:
                    pass
        return role

    async def _log_action(self, guild: discord.Guild, embed: discord.Embed):
        from handlers.json_handler import get_guild_config
        cfg = get_guild_config(guild.id)
        ch_id = cfg.get("log_channel")
        if ch_id:
            channel = guild.get_channel(int(ch_id))
            if channel:
                await channel.send(embed=embed)

    # ── !ban ──────────────────────────────────────────────────────────────────

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Ban a member from the server."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You can't ban someone with equal or higher role!")
        await member.ban(reason=f"{ctx.author} — {reason}")
        embed = discord.Embed(title="🔨 Member Banned", color=COLOR_ERROR)
        embed.add_field(name="Member", value=str(member), inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        await self._log_action(ctx.guild, embed)

    # ── !unban ────────────────────────────────────────────────────────────────

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, *, user_id: int):
        """Unban a user by ID."""
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=f"Unbanned by {ctx.author}")
            embed = discord.Embed(title="✅ Member Unbanned", description=str(user), color=COLOR_SUCCESS)
            await ctx.send(embed=embed)
        except discord.NotFound:
            await ctx.send("❌ User not found in ban list.")

    # ── !kick ─────────────────────────────────────────────────────────────────

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You can't kick someone with equal or higher role!")
        await member.kick(reason=f"{ctx.author} — {reason}")
        embed = discord.Embed(title="👢 Member Kicked", color=COLOR_WARNING)
        embed.add_field(name="Member", value=str(member), inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        await self._log_action(ctx.guild, embed)

    # ── !mute / !unmute ───────────────────────────────────────────────────────

    @commands.command(name="mute", aliases=["silence"])
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member,
                   duration: int = None, *, reason: str = "No reason provided"):
        """Mute a member. Optionally specify duration in minutes."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        role = await self._get_or_create_mute_role(ctx.guild)
        if role in member.roles:
            return await ctx.send(f"❌ {member.mention} is already muted.")
        await member.add_roles(role, reason=reason)
        dur_str = f"for **{duration}m**" if duration else "indefinitely"
        embed = discord.Embed(title="🔇 Member Muted", color=COLOR_WARNING)
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Duration", value=dur_str, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        await self._log_action(ctx.guild, embed)

        if duration:
            await asyncio.sleep(duration * 60)
            if role in member.roles:
                await member.remove_roles(role, reason="Mute expired")

    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Unmute a member."""
        role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
        if not role or role not in member.roles:
            return await ctx.send(f"❌ {member.mention} is not muted.")
        await member.remove_roles(role)
        embed = discord.Embed(title="🔊 Member Unmuted", description=member.mention, color=COLOR_SUCCESS)
        await ctx.send(embed=embed)

    # ── !timeout ──────────────────────────────────────────────────────────────

    @commands.command(name="timeout", aliases=["to"])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member,
                      minutes: int = 5, *, reason: str = "No reason provided"):
        """Timeout a member for N minutes (uses Discord's native timeout)."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        embed = discord.Embed(title="⏱️ Member Timed Out", color=COLOR_WARNING)
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Duration", value=f"{minutes} minutes", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        await self._log_action(ctx.guild, embed)

    # ── !warn ─────────────────────────────────────────────────────────────────

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a member and log it."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
                (member.id, ctx.guild.id, ctx.author.id, reason)
            )
            await db.commit()
            async with db.execute(
                "SELECT COUNT(*) FROM warnings WHERE user_id=? AND guild_id=?",
                (member.id, ctx.guild.id)
            ) as cursor:
                count = (await cursor.fetchone())[0]

        embed = discord.Embed(title="⚠️ Warning Issued", color=COLOR_WARNING)
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Total warnings: {count}")
        await ctx.send(embed=embed)
        await self._log_action(ctx.guild, embed)

        try:
            await member.send(
                embed=discord.Embed(
                    title=f"⚠️ Warning in {ctx.guild.name}",
                    description=f"**Reason:** {reason}\n**Total warnings:** {count}",
                    color=COLOR_WARNING,
                )
            )
        except discord.Forbidden:
            pass

    # ── !warnings ─────────────────────────────────────────────────────────────

    @commands.command(name="warnings", aliases=["warns"])
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        """View all warnings for a member."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, moderator_id, reason, created_at FROM warnings WHERE user_id=? AND guild_id=? ORDER BY created_at DESC LIMIT 10",
                (member.id, ctx.guild.id)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send(f"✅ {member.mention} has no warnings.")

        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=COLOR_WARNING)
        for wid, mod_id, reason, ts in rows:
            mod = ctx.guild.get_member(mod_id)
            embed.add_field(
                name=f"#{wid} — {ts}",
                value=f"**Mod:** {mod.mention if mod else mod_id}\n**Reason:** {reason}",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── !clearwarn ────────────────────────────────────────────────────────────

    @commands.command(name="clearwarn", aliases=["delwarn"])
    @commands.has_permissions(manage_messages=True)
    async def clearwarn(self, ctx: commands.Context, member: discord.Member):
        """Clear all warnings for a member."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM warnings WHERE user_id=? AND guild_id=?",
                (member.id, ctx.guild.id)
            )
            await db.commit()
        await ctx.send(f"✅ Cleared all warnings for {member.mention}.")

    # ── !purge ────────────────────────────────────────────────────────────────

    @commands.command(name="purge", aliases=["clear", "prune"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 10,
                    member: discord.Member = None):
        """Delete N messages (optionally from a specific member)."""
        if amount < 1 or amount > 200:
            return await ctx.send("❌ Amount must be between 1 and 200.")
        await ctx.message.delete()
        check = (lambda m: m.author == member) if member else None
        deleted = await ctx.channel.purge(limit=amount, check=check)
        embed = discord.Embed(
            title="🗑️ Messages Purged",
            description=f"Deleted **{len(deleted)}** message(s){f' from {member.mention}' if member else ''}.",
            color=COLOR_SUCCESS,
        )
        await ctx.send(embed=embed, delete_after=5)

    # ── !slowmode ─────────────────────────────────────────────────────────────

    @commands.command(name="slowmode", aliases=["sm"])
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int = 0):
        """Set slowmode (0 to disable)."""
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("✅ Slowmode **disabled**.", delete_after=5)
        else:
            await ctx.send(f"✅ Slowmode set to **{seconds}s**.", delete_after=5)

    # ── !lock / !unlock ───────────────────────────────────────────────────────

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Lock a channel (disables sending messages for @everyone)."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔒 Channel Locked", description=ch.mention, color=COLOR_ERROR)
        await ctx.send(embed=embed)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Unlock a channel."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔓 Channel Unlocked", description=ch.mention, color=COLOR_SUCCESS)
        await ctx.send(embed=embed)

    # ── !nick ─────────────────────────────────────────────────────────────────

    @commands.command(name="nick", aliases=["nickname"])
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str = None):
        """Change a member's nickname."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        old = member.display_name
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Changed **{old}** → **{nickname or member.name}**", delete_after=8)

    # ── !role ─────────────────────────────────────────────────────────────────

    @commands.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        """Add or remove a role from a member (toggles)."""
        if is_protected(member):
            return await ctx.send("🛡️ That user is protected and cannot be moderated.")
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.send(f"➖ Removed **{role.name}** from {member.mention}", delete_after=5)
        else:
            await member.add_roles(role)
            await ctx.send(f"➕ Added **{role.name}** to {member.mention}", delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
