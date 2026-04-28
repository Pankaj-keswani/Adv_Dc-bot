"""
extras.py — Bonus advanced features:
  - Auto-moderation (bad words, anti-spam, link filter)
  - Leveling system (XP per message, level-up announcements)
  - Giveaway system
  - Reminders
  - Ticket system
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import random
import re
import time
from datetime import timedelta
from collections import defaultdict
from config.settings import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)
from handlers.json_handler import get_guild_config
import logging

log = logging.getLogger("bot")
DB_PATH = "data/economy.db"



URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


async def _init_extras_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                remind_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                prize TEXT NOT NULL,
                winners INTEGER DEFAULT 1,
                ends_at REAL NOT NULL,
                host_id INTEGER NOT NULL,
                ended INTEGER DEFAULT 0
            )
        """)
        await db.commit()


class Extras(commands.Cog):
    """⚡ Advanced features: leveling, giveaways, reminders, tickets, automod."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.xp_cooldowns: dict[int, float] = {}  # user_id: last_xp_time
        self.spam_tracker: dict[int, list] = defaultdict(list)  # user_id: [timestamps]

    async def cog_load(self):
        await _init_extras_db()
        self.bot.loop.create_task(self._reminder_loop())
        self.bot.loop.create_task(self._giveaway_loop())

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO-MODERATION
    # ─────────────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = get_guild_config(message.guild.id)

        # Blacklist check
        if message.author.id in cfg.get("blacklisted_users", []):
            try:
                await message.delete()
            except Exception:
                pass
            return

        # Bad word filter
        bad_words: list = cfg.get("bad_words", [])
        if bad_words:
            content_lower = message.content.lower()
            if any(word in content_lower for word in bad_words):
                try:
                    await message.delete()
                    await message.channel.send(
                        f"🚫 {message.author.mention}, watch your language!", delete_after=5
                    )
                except Exception:
                    pass
                return

        # Link filter
        if cfg.get("link_filter") and URL_PATTERN.search(message.content):
            if not message.author.guild_permissions.manage_messages:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"🔗 {message.author.mention}, links are not allowed!", delete_after=5
                    )
                except Exception:
                    pass
                return

        # Anti-spam (5 messages in 5 seconds)
        if cfg.get("anti_spam"):
            now = time.time()
            history = self.spam_tracker[message.author.id]
            history.append(now)
            self.spam_tracker[message.author.id] = [t for t in history if now - t <= 5]
            if len(self.spam_tracker[message.author.id]) > 5:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, slow down! Anti-spam triggered.", delete_after=5
                    )
                except Exception:
                    pass
                return




    # ─────────────────────────────────────────────────────────────────────────
    # GIVEAWAYS
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.describe(
        prize="What are you giving away?",
        duration="Duration in minutes",
        winners="Number of winners (default: 1)",
        channel="Channel to host the giveaway",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str,
                       duration: int, winners: int = 1,
                       channel: discord.TextChannel = None):
        """Start a giveaway!"""
        ch = channel or interaction.channel
        ends_at = time.time() + (duration * 60)
        embed = discord.Embed(
            title="🎉 GIVEAWAY!",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(ends_at)}:R>\n"
                f"**Hosted by:** {interaction.user.mention}\n\n"
                "React with 🎉 to enter!"
            ),
            color=COLOR_SUCCESS,
        )
        embed.set_footer(text=f"Ends at")
        embed.timestamp = discord.utils.utcnow() + timedelta(minutes=duration)

        msg = await ch.send(embed=embed)
        await msg.add_reaction("🎉")
        await interaction.response.send_message(f"✅ Giveaway started in {ch.mention}!", ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners, ends_at, host_id) VALUES (?,?,?,?,?,?,?)",
                (interaction.guild_id, ch.id, msg.id, prize, winners, ends_at, interaction.user.id)
            )
            await db.commit()

    async def _giveaway_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = time.time()
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id, guild_id, channel_id, message_id, prize, winners, host_id FROM giveaways WHERE ends_at <= ? AND ended=0",
                    (now,)
                ) as cursor:
                    rows = await cursor.fetchall()

                for row in rows:
                    gid, guild_id, channel_id, message_id, prize, winner_count, host_id = row
                    await db.execute("UPDATE giveaways SET ended=1 WHERE id=?", (gid,))
                    await db.commit()

                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    try:
                        msg = await channel.fetch_message(message_id)
                        reaction = discord.utils.get(msg.reactions, emoji="🎉")
                        if reaction:
                            users = [u async for u in reaction.users() if not u.bot]
                            if users:
                                picked = random.sample(users, min(winner_count, len(users)))
                                winners_str = " ".join(u.mention for u in picked)
                                await channel.send(
                                    f"🎉 **Giveaway Ended!**\n"
                                    f"**Prize:** {prize}\n"
                                    f"**Winner(s):** {winners_str}\n"
                                    f"Congratulations! 🎊"
                                )
                            else:
                                await channel.send(f"🎉 Giveaway for **{prize}** ended — no entries!")
                    except Exception as e:
                        log.error("Giveaway end error: %s", e)

            await asyncio.sleep(15)

    # ─────────────────────────────────────────────────────────────────────────
    # REMINDERS
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(name="remind", description="Set a reminder")
    @app_commands.describe(
        time_str="Time e.g. 10m, 2h, 1d",
        message="What to remind you about",
    )
    async def remind(self, interaction: discord.Interaction, time_str: str, message: str):
        """Set a reminder."""
        seconds = self._parse_time(time_str)
        if seconds is None:
            return await interaction.response.send_message(
                "❌ Invalid time format. Use: `10m`, `2h`, `1d`", ephemeral=True
            )

        remind_at = time.time() + seconds
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO reminders (user_id, channel_id, message, remind_at) VALUES (?,?,?,?)",
                (interaction.user.id, interaction.channel_id, message, remind_at)
            )
            await db.commit()

        from datetime import timedelta as td
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        if s: parts.append(f"{s}s")
        await interaction.response.send_message(
            f"⏰ Reminder set for **{' '.join(parts)}** from now! I'll ping you here.", ephemeral=True
        )

    def _parse_time(self, s: str) -> int | None:
        total = 0
        parts = re.findall(r"(\d+)([smhd])", s.lower())
        if not parts:
            return None
        mapping = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        for amount, unit in parts:
            total += int(amount) * mapping[unit]
        return total if total > 0 else None

    async def _reminder_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = time.time()
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id, user_id, channel_id, message FROM reminders WHERE remind_at <= ?",
                    (now,)
                ) as cursor:
                    rows = await cursor.fetchall()
                for rid, user_id, channel_id, message in rows:
                    await db.execute("DELETE FROM reminders WHERE id=?", (rid,))
                    await db.commit()
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.send(f"⏰ <@{user_id}> Reminder: **{message}**")
                        except Exception:
                            pass
            await asyncio.sleep(10)

    # ─────────────────────────────────────────────────────────────────────────
    # TICKET SYSTEM
    # ─────────────────────────────────────────────────────────────────────────

    @app_commands.command(name="ticket", description="Open a support ticket")
    @app_commands.describe(reason="Reason for the ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str = "No reason specified"):
        """Create a private support ticket channel."""
        guild = interaction.guild
        category = None
        cfg = get_guild_config(guild.id)
        cat_id = cfg.get("ticket_category")
        if cat_id:
            category = guild.get_channel(int(cat_id))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket by {interaction.user}",
        )

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Hello {interaction.user.mention}!\n"
                f"**Reason:** {reason}\n\n"
                "A staff member will assist you shortly.\n"
                "Use the button below to close the ticket."
            ),
            color=COLOR_PRIMARY,
        )

        close_view = TicketCloseView()
        await channel.send(embed=embed, view=close_view)
        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}", ephemeral=True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # AUTOMOD CONFIGURATION
    # ─────────────────────────────────────────────────────────────────────────

    @commands.command(name="addword", aliases=["filterword"])
    @commands.has_permissions(manage_guild=True)
    async def addword(self, ctx: commands.Context, *, word: str):
        """Add a word to the bad words filter."""
        from handlers.json_handler import update_guild_key
        cfg = get_guild_config(ctx.guild.id)
        bad_words = cfg.get("bad_words", [])
        if word.lower() not in bad_words:
            bad_words.append(word.lower())
            await update_guild_key(ctx.guild.id, "bad_words", bad_words)
        await ctx.send(f"✅ Added `{word}` to the word filter.", delete_after=5)

    @commands.command(name="removeword")
    @commands.has_permissions(manage_guild=True)
    async def removeword(self, ctx: commands.Context, *, word: str):
        """Remove a word from the bad words filter."""
        from handlers.json_handler import update_guild_key
        cfg = get_guild_config(ctx.guild.id)
        bad_words = cfg.get("bad_words", [])
        if word.lower() in bad_words:
            bad_words.remove(word.lower())
            await update_guild_key(ctx.guild.id, "bad_words", bad_words)
        await ctx.send(f"✅ Removed `{word}` from the word filter.", delete_after=5)

    @commands.command(name="togglelinks")
    @commands.has_permissions(manage_guild=True)
    async def togglelinks(self, ctx: commands.Context):
        """Toggle the link filter."""
        from handlers.json_handler import update_guild_key
        cfg = get_guild_config(ctx.guild.id)
        new_val = not cfg.get("link_filter", False)
        await update_guild_key(ctx.guild.id, "link_filter", new_val)
        await ctx.send(f"🔗 Link filter {'**enabled**' if new_val else '**disabled**'}.")

    @commands.command(name="toggleantispam")
    @commands.has_permissions(manage_guild=True)
    async def toggleantispam(self, ctx: commands.Context):
        """Toggle the anti-spam system."""
        from handlers.json_handler import update_guild_key
        cfg = get_guild_config(ctx.guild.id)
        new_val = not cfg.get("anti_spam", True)
        await update_guild_key(ctx.guild.id, "anti_spam", new_val)
        await ctx.send(f"🛡️ Anti-spam {'**enabled**' if new_val else '**disabled**'}.")


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.Forbidden:
            await interaction.channel.send("❌ I don't have permission to delete this channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Extras(bot))
