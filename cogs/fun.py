"""
fun.py — Fun commands: jokes, memes, 8ball, roast, trivia, polls, coinflip.
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import aiohttp
from config.settings import COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
import logging

log = logging.getLogger("bot")

EIGHT_BALL_RESPONSES = [
    "✅ It is certain.", "✅ It is decidedly so.", "✅ Without a doubt.",
    "✅ Yes, definitely!", "✅ You may rely on it.", "✅ As I see it, yes.",
    "✅ Most likely.", "✅ Outlook good.", "✅ Yes.", "✅ Signs point to yes.",
    "🤔 Reply hazy, try again.", "🤔 Ask again later.", "🤔 Better not tell you now.",
    "🤔 Cannot predict now.", "🤔 Concentrate and ask again.",
    "❌ Don't count on it.", "❌ My reply is no.", "❌ My sources say no.",
    "❌ Outlook not so good.", "❌ Very doubtful.",
]

ROASTS = [
    "I'd roast you, but my mom said I'm not allowed to burn trash.",
    "You're like a cloud — when you disappear, it's a beautiful day.",
    "I'd call you a tool, but even tools are useful.",
    "You're the human equivalent of a participation trophy.",
    "I've seen better comebacks in deodorant commercials.",
    "Your WiFi signal has more personality than you do.",
    "You're proof that evolution isn't always progress.",
]

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything!"),
    ("Why did the scarecrow win an award?", "Because he was outstanding in his field!"),
    ("I told my wife she was drawing her eyebrows too high.", "She looked surprised."),
    ("Why don't programmers like nature?", "It has too many bugs."),
    ("What do you call a fake noodle?", "An Impasta!"),
    ("Why did the bicycle fall over?", "Because it was two-tired."),
    ("What did the ocean say to the beach?", "Nothing, it just waved."),
]

TRIVIA_QUESTIONS = [
    {"q": "What is the capital of France?", "a": "paris", "options": ["London", "Berlin", "Paris", "Madrid"]},
    {"q": "What is 7 x 8?", "a": "56", "options": ["54", "56", "58", "64"]},
    {"q": "What planet is known as the Red Planet?", "a": "mars", "options": ["Venus", "Jupiter", "Mars", "Saturn"]},
    {"q": "Who wrote 'Romeo and Juliet'?", "a": "shakespeare", "options": ["Dickens", "Shakespeare", "Twain", "Poe"]},
    {"q": "What is the largest ocean?", "a": "pacific", "options": ["Atlantic", "Indian", "Arctic", "Pacific"]},
    {"q": "How many sides does a hexagon have?", "a": "6", "options": ["5", "6", "7", "8"]},
    {"q": "What is the chemical symbol for gold?", "a": "au", "options": ["Go", "Gd", "Au", "Ag"]},
]


class Fun(commands.Cog):
    """😄 Fun commands to keep the server lively!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ── !8ball ────────────────────────────────────────────────────────────────

    @commands.command(name="8ball", aliases=["8b", "ask8"])
    async def eightball(self, ctx: commands.Context, *, question: str):
        """Ask the magic 8-ball a question."""
        response = random.choice(EIGHT_BALL_RESPONSES)
        embed = discord.Embed(color=COLOR_PRIMARY)
        embed.add_field(name="🎱 Question", value=question, inline=False)
        embed.add_field(name="Answer", value=response, inline=False)
        await ctx.send(embed=embed)

    # ── !joke ─────────────────────────────────────────────────────────────────

    @commands.command(name="joke")
    async def joke(self, ctx: commands.Context):
        """Get a random joke."""
        setup, punchline = random.choice(JOKES)
        embed = discord.Embed(title="😂 Joke Time!", color=COLOR_PRIMARY)
        embed.add_field(name="Setup", value=setup, inline=False)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(2)
        embed.add_field(name="Punchline", value=f"||{punchline}||", inline=False)
        await msg.edit(embed=embed)

    # ── !roast ────────────────────────────────────────────────────────────────

    @commands.command(name="roast", aliases=["burn"])
    async def roast(self, ctx: commands.Context, member: discord.Member = None):
        """Roast someone (or yourself)."""
        target = member or ctx.author
        roast = random.choice(ROASTS)
        embed = discord.Embed(
            title=f"🔥 Roasting {target.display_name}",
            description=roast,
            color=COLOR_ERROR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    # ── !coinflip ─────────────────────────────────────────────────────────────

    @commands.command(name="coinflip", aliases=["flip", "cf"])
    async def coinflip(self, ctx: commands.Context):
        """Flip a coin."""
        result = random.choice(["🪙 **Heads!**", "🪙 **Tails!**"])
        await ctx.send(result)

    # ── !dice ─────────────────────────────────────────────────────────────────

    @commands.command(name="dice", aliases=["roll"])
    async def dice(self, ctx: commands.Context, sides: int = 6):
        """Roll a dice (default: 6-sided)."""
        if sides < 2:
            return await ctx.send("❌ Dice must have at least 2 sides.")
        result = random.randint(1, sides)
        await ctx.send(f"🎲 You rolled a **{result}** (d{sides})")

    # ── !avatar ───────────────────────────────────────────────────────────────

    @commands.command(name="avatar", aliases=["pfp", "av"])
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        """Show a member's avatar."""
        target = member or ctx.author
        embed = discord.Embed(title=f"{target.display_name}'s Avatar", color=COLOR_PRIMARY)
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    # ── !meme ─────────────────────────────────────────────────────────────────

    @commands.command(name="meme")
    async def meme(self, ctx: commands.Context):
        """Get a random meme from Reddit."""
        try:
            async with self.session.get(
                "https://www.reddit.com/r/memes/random/.json",
                headers={"User-Agent": "DiscordBot/1.0"}
            ) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Could not fetch meme.")
                data = await resp.json()
                post = data[0]["data"]["children"][0]["data"]
                embed = discord.Embed(title=post["title"], color=COLOR_PRIMARY)
                embed.set_image(url=post.get("url", ""))
                embed.set_footer(text=f"👍 {post.get('ups', 0):,} | r/memes")
                await ctx.send(embed=embed)
        except Exception as e:
            log.error("Meme fetch error: %s", e)
            await ctx.send("❌ Could not fetch a meme right now.")

    # ── !trivia ───────────────────────────────────────────────────────────────

    @commands.command(name="trivia", aliases=["quiz"])
    async def trivia(self, ctx: commands.Context):
        """Answer a trivia question (30 seconds)."""
        q = random.choice(TRIVIA_QUESTIONS)
        options = q["options"].copy()
        random.shuffle(options)
        letters = ["🇦", "🇧", "🇨", "🇩"]
        correct_letter = letters[options.index(next(o for o in options if o.lower() == q["a"].lower() or q["a"].lower() in o.lower()))]

        embed = discord.Embed(title="🧠 Trivia Time!", description=q["q"], color=COLOR_PRIMARY)
        for i, opt in enumerate(options):
            embed.add_field(name=letters[i], value=opt, inline=True)
        embed.set_footer(text="You have 30 seconds! Type the letter (A/B/C/D)")
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.author == ctx.author and
                m.channel == ctx.channel and
                m.content.upper() in ["A", "B", "C", "D"]
            )

        try:
            guess = await self.bot.wait_for("message", timeout=30.0, check=check)
            guessed_letter = letters[["A", "B", "C", "D"].index(guess.content.upper())]
            if guessed_letter == correct_letter:
                await ctx.send(f"✅ **Correct!** The answer was: **{options[letters.index(correct_letter)]}**")
            else:
                await ctx.send(f"❌ **Wrong!** The correct answer was {correct_letter} — **{options[letters.index(correct_letter)]}**")
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! The answer was {correct_letter} — **{options[letters.index(correct_letter)]}**")

    # ── /poll ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="poll", description="Create a quick poll")
    @app_commands.describe(question="Poll question", option1="Option A", option2="Option B",
                           option3="Option C (optional)", option4="Option D (optional)")
    async def poll(self, interaction: discord.Interaction, question: str,
                   option1: str, option2: str,
                   option3: str = None, option4: str = None):
        """Create an emoji-reaction poll."""
        options = [o for o in [option1, option2, option3, option4] if o]
        letters = ["🇦", "🇧", "🇨", "🇩"]
        embed = discord.Embed(title=f"📊 Poll: {question}", color=COLOR_PRIMARY)
        embed.description = "\n".join(f"{letters[i]} {opt}" for i, opt in enumerate(options))
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(letters[i])

    # ── !quote ────────────────────────────────────────────────────────────────

    @commands.command(name="quote", aliases=["inspiration"])
    async def quote(self, ctx: commands.Context):
        """Get an inspirational quote."""
        try:
            async with self.session.get("https://zenquotes.io/api/random") as resp:
                data = await resp.json()
                q = data[0]
                embed = discord.Embed(
                    description=f"*\"{q['q']}\"*\n\n— **{q['a']}**",
                    color=COLOR_SUCCESS,
                )
                await ctx.send(embed=embed)
        except Exception:
            await ctx.send("❌ Could not fetch a quote.")

    # ── !choose ───────────────────────────────────────────────────────────────

    @commands.command(name="choose", aliases=["pick"])
    async def choose(self, ctx: commands.Context, *options: str):
        """Choose randomly between options. Separate with spaces."""
        if len(options) < 2:
            return await ctx.send("❌ Give me at least 2 options!")
        pick = random.choice(options)
        await ctx.send(f"🎯 I choose: **{pick}**")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
