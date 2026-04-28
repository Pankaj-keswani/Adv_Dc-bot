"""
owner.py — Owner-only commands: eval, reload, shutdown, announce, blacklist, stats.
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import textwrap
import traceback
import io
import contextlib
from config.settings import OWNER_IDS, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_PRIMARY
from handlers.json_handler import get_guild_config, update_guild_key
import logging

log = logging.getLogger("bot")


def is_owner():
    async def predicate(ctx: commands.Context):
        return ctx.author.id in OWNER_IDS or await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)


class Owner(commands.Cog):
    """👑 Owner-only administrative commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !reload ───────────────────────────────────────────────────────────────

    @commands.command(name="reload", hidden=True)
    @is_owner()
    async def reload(self, ctx: commands.Context, *, cog: str):
        """Reload a cog."""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Reloaded `cogs.{cog}`")
        except Exception as e:
            await ctx.send(f"❌ Failed: `{e}`")

    @commands.command(name="load", hidden=True)
    @is_owner()
    async def load(self, ctx: commands.Context, *, cog: str):
        """Load a cog."""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Loaded `cogs.{cog}`")
        except Exception as e:
            await ctx.send(f"❌ Failed: `{e}`")

    @commands.command(name="unload", hidden=True)
    @is_owner()
    async def unload(self, ctx: commands.Context, *, cog: str):
        """Unload a cog."""
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Unloaded `cogs.{cog}`")
        except Exception as e:
            await ctx.send(f"❌ Failed: `{e}`")

    @commands.command(name="reloadall", hidden=True)
    @is_owner()
    async def reloadall(self, ctx: commands.Context):
        """Reload all cogs."""
        results = []
        cogs = list(self.bot.extensions.keys())
        for cog in cogs:
            try:
                await self.bot.reload_extension(cog)
                results.append(f"✅ `{cog}`")
            except Exception as e:
                results.append(f"❌ `{cog}` — {e}")
        await ctx.send("\n".join(results) or "No cogs loaded.")

    # ── !eval ─────────────────────────────────────────────────────────────────

    @commands.command(name="eval", aliases=["exec", "py"], hidden=True)
    @is_owner()
    async def eval_cmd(self, ctx: commands.Context, *, code: str):
        """Evaluate Python code."""
        code = code.strip("` \n")
        if code.startswith("python"):
            code = code[6:]

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "guild": ctx.guild,
            "author": ctx.author,
            "discord": discord,
            "__import__": __import__,
        }

        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exec_code = f"async def __eval():\n{textwrap.indent(code, '    ')}"
                exec(exec_code, env)
                result = await env["__eval"]()
        except Exception:
            result = traceback.format_exc()

        output = stdout.getvalue()
        final = f"{output}\n{result}" if result else output

        embed = discord.Embed(title="📟 Eval Result", color=COLOR_SUCCESS if not isinstance(result, Exception) else COLOR_ERROR)
        embed.add_field(name="Input", value=f"```py\n{code[:512]}```", inline=False)
        if final:
            embed.add_field(name="Output", value=f"```py\n{str(final)[:512]}```", inline=False)
        await ctx.send(embed=embed)

    # ── !shutdown ─────────────────────────────────────────────────────────────

    @commands.command(name="shutdown", aliases=["die", "quit"], hidden=True)
    @is_owner()
    async def shutdown(self, ctx: commands.Context):
        """Shut down the bot gracefully."""
        await ctx.send("👋 Shutting down... Goodbye!")
        await self.bot.close()

    # ── !announce ─────────────────────────────────────────────────────────────

    @commands.command(name="announce", aliases=["broadcast"], hidden=True)
    @is_owner()
    async def announce(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        """Send an announcement to a specific channel."""
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=COLOR_PRIMARY,
        )
        embed.set_footer(text=f"From {ctx.author}")
        await channel.send(embed=embed)
        await ctx.send(f"✅ Announcement sent to {channel.mention}", delete_after=5)

    # ── !dm ───────────────────────────────────────────────────────────────────

    @commands.command(name="dm", hidden=True)
    @is_owner()
    async def dm_user(self, ctx: commands.Context, user: discord.User, *, message: str):
        """DM any user."""
        try:
            await user.send(f"📬 **Message from bot owner:**\n{message}")
            await ctx.send(f"✅ DM sent to **{user}**", delete_after=5)
        except discord.Forbidden:
            await ctx.send("❌ Cannot DM this user (DMs closed).")

    # ── !blacklist ────────────────────────────────────────────────────────────

    @commands.command(name="blacklist", hidden=True)
    @is_owner()
    async def blacklist(self, ctx: commands.Context, action: str, user: discord.User):
        """Blacklist or unblacklist a user globally."""
        cfg = get_guild_config(ctx.guild.id)
        bl: list = cfg.get("blacklisted_users", [])
        if action.lower() in ("add", "block"):
            if user.id not in bl:
                bl.append(user.id)
                await update_guild_key(ctx.guild.id, "blacklisted_users", bl)
            await ctx.send(f"🚫 **{user}** has been blacklisted.")
        elif action.lower() in ("remove", "unblock"):
            if user.id in bl:
                bl.remove(user.id)
                await update_guild_key(ctx.guild.id, "blacklisted_users", bl)
            await ctx.send(f"✅ **{user}** has been unblacklisted.")

    # ── !setwelcome / !setfarewell / setlogchannel ────────────────────────────

    @commands.command(name="setwelcome", hidden=True)
    @commands.has_permissions(administrator=True)
    async def setwelcome(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the welcome channel."""
        await update_guild_key(ctx.guild.id, "welcome_channel", str(channel.id))
        await ctx.send(f"✅ Welcome channel set to {channel.mention}")

    @commands.command(name="setfarewell", hidden=True)
    @commands.has_permissions(administrator=True)
    async def setfarewell(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the farewell channel."""
        await update_guild_key(ctx.guild.id, "farewell_channel", str(channel.id))
        await ctx.send(f"✅ Farewell channel set to {channel.mention}")

    @commands.command(name="setlog", hidden=True)
    @commands.has_permissions(administrator=True)
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the moderation log channel."""
        await update_guild_key(ctx.guild.id, "log_channel", str(channel.id))
        await ctx.send(f"✅ Log channel set to {channel.mention}")

    @commands.command(name="setprefix", hidden=True)
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Change the bot prefix for this server."""
        await update_guild_key(ctx.guild.id, "prefix", prefix)
        await ctx.send(f"✅ Prefix changed to `{prefix}`")

    # ── !synccmds ─────────────────────────────────────────────────────────────

    @commands.command(name="sync", hidden=True)
    @is_owner()
    async def sync_commands(self, ctx: commands.Context, guild_id: int = None):
        """Sync slash commands globally or to a guild."""
        if guild_id:
            guild = discord.Object(id=guild_id)
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Synced {len(synced)} commands to guild `{guild_id}`")
        else:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} commands globally")

    # ── !status ───────────────────────────────────────────────────────────────

    @commands.command(name="setstatus", hidden=True)
    @is_owner()
    async def setstatus(self, ctx: commands.Context, activity_type: str, *, text: str):
        """Change the bot's status. Types: playing, watching, listening, streaming"""
        types = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "streaming": discord.ActivityType.streaming,
        }
        atype = types.get(activity_type.lower(), discord.ActivityType.playing)
        await self.bot.change_presence(activity=discord.Activity(type=atype, name=text))
        await ctx.send(f"✅ Status set to `{activity_type} {text}`", delete_after=5)

    @commands.command(name="testwelcome", hidden=True)
    @is_owner()
    async def testwelcome(self, ctx: commands.Context):
        """Test the custom welcome image generation."""
        from handlers.event_handler import EventHandler
        # Trigger the event manually for the author
        cog = self.bot.get_cog("EventHandler")
        if cog:
            await cog.on_member_join(ctx.author)
            await ctx.send("✅ Triggered welcome event for you!")
        else:
            await ctx.send("❌ EventHandler cog not found.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
