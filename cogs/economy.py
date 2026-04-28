"""
economy.py — Full economy system with balance, daily, work, gamble, shop, leaderboard.
Uses SQLite via aiosqlite for persistent storage.
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import random
import asyncio
from datetime import datetime, timedelta
from config.settings import (
    CURRENCY_NAME, CURRENCY_EMOJI, DAILY_AMOUNT,
    WORK_MIN, WORK_MAX, GAMBLE_MIN_BET,
    COLOR_ECONOMY, COLOR_ERROR, COLOR_SUCCESS
)
import logging

log = logging.getLogger("bot")
DB_PATH = "data/economy.db"

WORK_MESSAGES = [
    "You worked as a software developer and earned",
    "You delivered pizza and earned",
    "You won a hackathon and received",
    "You streamed on Twitch and made",
    "You sold memes online and got",
    "You mined crypto and earned",
    "You did freelance design work and earned",
]

SHOP_ITEMS = {
    "vip_role_badge": {"name": "⭐ VIP Badge", "price": 5000, "description": "Exclusive VIP bragging rights"},
    "color_role":     {"name": "🎨 Custom Color", "price": 2500, "description": "A custom color role"},
    "lucky_charm":    {"name": "🍀 Lucky Charm", "price": 1000, "description": "+10% gamble winnings for 24h"},
    "rob_shield":     {"name": "🛡️ Rob Shield", "price": 1500, "description": "Protects you from being robbed for 12h"},
}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT NULL,
                last_work TEXT DEFAULT NULL,
                last_rob TEXT DEFAULT NULL,
                inventory TEXT DEFAULT '[]',
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.commit()


async def get_user(db: aiosqlite.Connection, user_id: int, guild_id: int) -> dict:
    async with db.execute(
        "SELECT * FROM economy WHERE user_id=? AND guild_id=?", (user_id, guild_id)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO economy (user_id, guild_id) VALUES (?, ?)",
            (user_id, guild_id)
        )
        await db.commit()
        return {"user_id": user_id, "guild_id": guild_id, "balance": 0, "bank": 0,
                "last_daily": None, "last_work": None,
                "last_rob": None, "inventory": "[]"}
    cols = ["user_id", "guild_id", "balance", "bank",
            "last_daily", "last_work", "last_rob", "inventory"]
    return dict(zip(cols, row))


async def update_balance(db: aiosqlite.Connection, user_id: int, guild_id: int, amount: int):
    await db.execute(
        "UPDATE economy SET balance = balance + ? WHERE user_id=? AND guild_id=?",
        (amount, user_id, guild_id)
    )
    await db.commit()


class Economy(commands.Cog):
    """💰 Economy system: earn, spend, gamble, and compete."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await init_db()

    # ── !balance ──────────────────────────────────────────────────────────────

    @commands.command(name="balance", aliases=["bal", "wallet"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your balance."""
        target = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, target.id, ctx.guild.id)
        embed = discord.Embed(title=f"💰 {target.display_name}'s Wallet", color=COLOR_ECONOMY)
        embed.add_field(name="Wallet", value=f"{CURRENCY_EMOJI} **{user['balance']:,}**", inline=True)
        embed.add_field(name="Bank", value=f"{CURRENCY_EMOJI} **{user['bank']:,}**", inline=True)
        embed.add_field(name="Total", value=f"{CURRENCY_EMOJI} **{user['balance'] + user['bank']:,}**", inline=True)
        embed.add_field(name="Level", value=f"⭐ **{user['level']}**", inline=True)
        embed.add_field(name="XP", value=f"✨ **{user['xp']}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    # ── !daily ────────────────────────────────────────────────────────────────

    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx: commands.Context):
        """Claim your daily reward."""
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, ctx.author.id, ctx.guild.id)
            await update_balance(db, ctx.author.id, ctx.guild.id, DAILY_AMOUNT)
        embed = discord.Embed(
            title="📅 Daily Reward",
            description=f"You claimed your daily {CURRENCY_EMOJI} **{DAILY_AMOUNT:,}**!\nCome back tomorrow for more.",
            color=COLOR_SUCCESS,
        )
        await ctx.send(embed=embed)

    @daily.error
    async def daily_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            remaining = timedelta(seconds=int(error.retry_after))
            h, rem = divmod(remaining.seconds, 3600)
            m, s = divmod(rem, 60)
            embed = discord.Embed(
                title="⏳ Already Claimed",
                description=f"Come back in **{h}h {m}m {s}s**",
                color=COLOR_ERROR,
            )
            await ctx.send(embed=embed)

    # ── !work ─────────────────────────────────────────────────────────────────

    @commands.command(name="work", aliases=["earn"])
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def work(self, ctx: commands.Context):
        """Work to earn coins (1hr cooldown)."""
        amount = random.randint(WORK_MIN, WORK_MAX)
        msg = random.choice(WORK_MESSAGES)
        async with aiosqlite.connect(DB_PATH) as db:
            await get_user(db, ctx.author.id, ctx.guild.id)
            await update_balance(db, ctx.author.id, ctx.guild.id, amount)
        embed = discord.Embed(
            title="💼 Work Done!",
            description=f"{msg} {CURRENCY_EMOJI} **{amount:,}**!",
            color=COLOR_ECONOMY,
        )
        await ctx.send(embed=embed)

    @work.error
    async def work_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.send(f"⏳ You can work again in **{m}m {s}s**", delete_after=8)

    # ── !gamble ───────────────────────────────────────────────────────────────

    @commands.command(name="gamble", aliases=["bet", "casino"])
    async def gamble(self, ctx: commands.Context, amount: str):
        """Gamble your coins. Win 2x or lose it all!"""
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, ctx.author.id, ctx.guild.id)
            bal = user["balance"]

            if amount.lower() == "all":
                bet = bal
            else:
                try:
                    bet = int(amount)
                except ValueError:
                    return await ctx.send("❌ Enter a valid amount or `all`.")

            if bet < GAMBLE_MIN_BET:
                return await ctx.send(f"❌ Minimum bet is {CURRENCY_EMOJI} **{GAMBLE_MIN_BET}**.")
            if bet > bal:
                return await ctx.send(f"❌ You only have {CURRENCY_EMOJI} **{bal:,}**.")

            win = random.random() < 0.48  # 48% win chance
            if win:
                winnings = bet
                await update_balance(db, ctx.author.id, ctx.guild.id, winnings)
                embed = discord.Embed(
                    title="🎰 You Won!",
                    description=f"You bet {CURRENCY_EMOJI} **{bet:,}** and won {CURRENCY_EMOJI} **{winnings:,}**!\n"
                                f"New Balance: {CURRENCY_EMOJI} **{bal + winnings:,}**",
                    color=COLOR_SUCCESS,
                )
            else:
                await update_balance(db, ctx.author.id, ctx.guild.id, -bet)
                embed = discord.Embed(
                    title="🎰 You Lost!",
                    description=f"You bet {CURRENCY_EMOJI} **{bet:,}** and lost it all!\n"
                                f"New Balance: {CURRENCY_EMOJI} **{bal - bet:,}**",
                    color=COLOR_ERROR,
                )
        await ctx.send(embed=embed)

    # ── !pay ──────────────────────────────────────────────────────────────────

    @commands.command(name="pay", aliases=["give"])
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Send coins to another user."""
        if member.bot:
            return await ctx.send("❌ Cannot pay bots.")
        if amount <= 0:
            return await ctx.send("❌ Amount must be positive.")
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, ctx.author.id, ctx.guild.id)
            if user["balance"] < amount:
                return await ctx.send(f"❌ Not enough {CURRENCY_NAME}.")
            await get_user(db, member.id, ctx.guild.id)
            await update_balance(db, ctx.author.id, ctx.guild.id, -amount)
            await update_balance(db, member.id, ctx.guild.id, amount)
        embed = discord.Embed(
            title="💸 Transfer Complete",
            description=f"{ctx.author.mention} sent {CURRENCY_EMOJI} **{amount:,}** to {member.mention}",
            color=COLOR_SUCCESS,
        )
        await ctx.send(embed=embed)

    # ── !leaderboard ──────────────────────────────────────────────────────────

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx: commands.Context):
        """Show the top 10 richest members."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, balance+bank as total FROM economy WHERE guild_id=? ORDER BY total DESC LIMIT 10",
                (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()

        embed = discord.Embed(title=f"🏆 {ctx.guild.name} Richest Members", color=COLOR_ECONOMY)
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines = []
        for i, (uid, total) in enumerate(rows):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"<User {uid}>"
            lines.append(f"{medals[i]} **{name}** — {CURRENCY_EMOJI} {total:,}")

        embed.description = "\n".join(lines) if lines else "*No data yet.*"
        await ctx.send(embed=embed)

    # ── !deposit / !withdraw ──────────────────────────────────────────────────

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit coins to your bank."""
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, ctx.author.id, ctx.guild.id)
            n = user["balance"] if amount.lower() == "all" else int(amount)
            if n > user["balance"]:
                return await ctx.send("❌ Not enough in wallet.")
            await db.execute(
                "UPDATE economy SET balance=balance-?, bank=bank+? WHERE user_id=? AND guild_id=?",
                (n, n, ctx.author.id, ctx.guild.id)
            )
            await db.commit()
        await ctx.send(f"🏦 Deposited {CURRENCY_EMOJI} **{n:,}** to your bank.", delete_after=8)

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw coins from your bank."""
        async with aiosqlite.connect(DB_PATH) as db:
            user = await get_user(db, ctx.author.id, ctx.guild.id)
            n = user["bank"] if amount.lower() == "all" else int(amount)
            if n > user["bank"]:
                return await ctx.send("❌ Not enough in bank.")
            await db.execute(
                "UPDATE economy SET bank=bank-?, balance=balance+? WHERE user_id=? AND guild_id=?",
                (n, n, ctx.author.id, ctx.guild.id)
            )
            await db.commit()
        await ctx.send(f"💵 Withdrew {CURRENCY_EMOJI} **{n:,}** to your wallet.", delete_after=8)

    # ── !shop ─────────────────────────────────────────────────────────────────

    @commands.command(name="shop")
    async def shop(self, ctx: commands.Context):
        """Browse the item shop."""
        embed = discord.Embed(title="🛒 Item Shop", color=COLOR_ECONOMY)
        for key, item in SHOP_ITEMS.items():
            embed.add_field(
                name=f"{item['name']} — {CURRENCY_EMOJI} {item['price']:,}",
                value=f"`!buy {key}` — {item['description']}",
                inline=False,
            )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
