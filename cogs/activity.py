"""
cogs/activity.py — Weekly gaming activity leaderboard.
Tracks time spent in voice channels and rewards active gamers.
"""

import discord
from discord.ext import commands, tasks
import aiosqlite
import time
from datetime import datetime, timedelta
import logging
from config.settings import COLOR_PRIMARY, COLOR_SUCCESS, COLOR_INFO

log = logging.getLogger("bot")
DB_PATH = "data/economy.db"

class Activity(commands.Cog):
    """🏆 Activity tracking for the gaming community."""

    def __init__(self, bot):
        self.bot = bot
        # user_id -> join_time
        self.sessions: dict[int, float] = {}
        self.reset_leaderboard.start()

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_activity (
                    user_id INTEGER,
                    guild_id INTEGER,
                    minutes INTEGER DEFAULT 0,
                    last_reset TEXT,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.commit()

    def cog_unload(self):
        self.reset_leaderboard.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        # 1. User Joined Voice
        if not before.channel and after.channel:
            self.sessions[member.id] = time.time()
            log.info(f"Started tracking voice session for {member}")

        # 2. User Left Voice
        elif before.channel and not after.channel:
            start_time = self.sessions.pop(member.id, None)
            if start_time:
                duration_seconds = time.time() - start_time
                duration_minutes = int(duration_seconds // 60)
                
                if duration_minutes > 0:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("""
                            INSERT INTO voice_activity (user_id, guild_id, minutes, last_reset)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                            minutes = minutes + ?
                        """, (member.id, member.guild.id, duration_minutes, datetime.now().date().isoformat(), duration_minutes))
                        await db.commit()
                        log.info(f"Added {duration_minutes}m to {member}")

    @commands.command(name="topgamers", aliases=["vclb", "topactivity"])
    async def topgamers(self, ctx: commands.Context):
        """Show the weekly voice activity leaderboard."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, minutes FROM voice_activity WHERE guild_id=? ORDER BY minutes DESC LIMIT 10",
                (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("🎮 No gaming activity recorded yet this week!")

        embed = discord.Embed(
            title="🏆 Weekly Gaming Leaderboard",
            description="Time spent in voice channels this week:",
            color=COLOR_PRIMARY
        )
        
        medals = ["🥇", "🥈", "🥉"] + ["🎮"] * 7
        lines = []
        for i, (uid, mins) in enumerate(rows):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            
            # Format time
            hrs, m = divmod(mins, 60)
            time_str = f"{hrs}h {m}m" if hrs > 0 else f"{m}m"
            
            lines.append(f"{medals[i]} **{name}** — {time_str}")

        embed.description += "\n\n" + "\n".join(lines)
        embed.set_footer(text="Resets every Monday at 00:00")
        await ctx.send(embed=embed)

    @commands.command(name="activity", aliases=["mystats"])
    async def activity(self, ctx: commands.Context, member: discord.Member = None):
        """Check your own weekly voice activity."""
        target = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT minutes FROM voice_activity WHERE user_id=? AND guild_id=?",
                (target.id, ctx.guild.id)
            ) as cursor:
                row = await cursor.fetchone()

        mins = row[0] if row else 0
        hrs, m = divmod(mins, 60)
        time_str = f"{hrs} hours and {m} minutes" if hrs > 0 else f"{m} minutes"

        embed = discord.Embed(title=f"🎮 {target.display_name}'s Activity", color=COLOR_INFO)
        embed.description = f"You have spent **{time_str}** in voice channels this week."
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @tasks.loop(hours=24)
    async def reset_leaderboard(self):
        """Resets the leaderboard every Monday at 00:00."""
        now = datetime.now()
        # Check if it's Monday (weekday 0)
        if now.weekday() == 0:
            log.info("Resetting weekly gaming leaderboard...")
            async with aiosqlite.connect(DB_PATH) as db:
                # Announcement before clearing? (optional, usually done in specific channel)
                await db.execute("DELETE FROM voice_activity")
                await db.commit()

    @reset_leaderboard.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Activity(bot))
