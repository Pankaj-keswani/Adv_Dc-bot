"""
games.py — Interactive games: TicTacToe, RPS, GuessNumber, Hangman.
"""

import discord
from discord.ext import commands
import random
import asyncio
from config.settings import COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR
import logging

log = logging.getLogger("bot")

# ── Hangman words ─────────────────────────────────────────────────────────────

HANGMAN_WORDS = [
    "python", "discord", "programming", "computer", "keyboard",
    "algorithm", "database", "developer", "framework", "javascript",
    "variable", "function", "exception", "interface", "recursive",
]

HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


class TicTacToeButton(discord.ui.Button):
    def __init__(self, row: int, col: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=row)
        self.row_pos = row
        self.col_pos = col

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user != view.current_player:
            return await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
        if self.label != "\u200b":
            return await interaction.response.send_message("❌ Cell already taken!", ephemeral=True)

        # Place mark
        mark = "❌" if view.current_player == view.player_x else "⭕"
        self.label = mark
        self.style = discord.ButtonStyle.danger if mark == "❌" else discord.ButtonStyle.primary
        self.disabled = True
        view.board[self.row_pos][self.col_pos] = mark

        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            embed = discord.Embed(
                title="🎮 Tic-Tac-Toe",
                description=f"🏆 **{interaction.user.display_name}** wins!",
                color=COLOR_SUCCESS,
            )
            return await interaction.response.edit_message(embed=embed, view=view)

        if view.is_draw():
            for child in view.children:
                child.disabled = True
            embed = discord.Embed(title="🎮 Tic-Tac-Toe", description="It's a **draw!**", color=COLOR_PRIMARY)
            return await interaction.response.edit_message(embed=embed, view=view)

        # Switch players
        view.current_player = view.player_o if view.current_player == view.player_x else view.player_x
        embed = discord.Embed(
            title="🎮 Tic-Tac-Toe",
            description=f"It's {view.current_player.mention}'s turn ({'⭕' if view.current_player == view.player_o else '❌'})",
            color=COLOR_PRIMARY,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class TicTacToeView(discord.ui.View):
    def __init__(self, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=120)
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x
        self.board = [["" for _ in range(3)] for _ in range(3)]
        for r in range(3):
            for c in range(3):
                self.add_item(TicTacToeButton(r, c))

    def check_winner(self) -> bool:
        b = self.board
        lines = [
            [b[0][0], b[0][1], b[0][2]],
            [b[1][0], b[1][1], b[1][2]],
            [b[2][0], b[2][1], b[2][2]],
            [b[0][0], b[1][0], b[2][0]],
            [b[0][1], b[1][1], b[2][1]],
            [b[0][2], b[1][2], b[2][2]],
            [b[0][0], b[1][1], b[2][2]],
            [b[0][2], b[1][1], b[2][0]],
        ]
        return any(len(set(line)) == 1 and line[0] != "" for line in lines)

    def is_draw(self) -> bool:
        return all(self.board[r][c] != "" for r in range(3) for c in range(3))


class Games(commands.Cog):
    """🎮 Interactive games for your server!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: set[int] = set()  # track active game channels

    # ── !tictactoe ────────────────────────────────────────────────────────────

    @commands.command(name="tictactoe", aliases=["ttt"])
    async def tictactoe(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge someone to TicTacToe!"""
        if opponent.bot:
            return await ctx.send("❌ You can't play against bots!")
        if opponent == ctx.author:
            return await ctx.send("❌ You can't play against yourself!")

        view = TicTacToeView(ctx.author, opponent)
        embed = discord.Embed(
            title="🎮 Tic-Tac-Toe",
            description=(
                f"**{ctx.author.mention}** (❌) vs **{opponent.mention}** (⭕)\n"
                f"It's {ctx.author.mention}'s turn!"
            ),
            color=COLOR_PRIMARY,
        )
        await ctx.send(embed=embed, view=view)

    # ── !rps ──────────────────────────────────────────────────────────────────

    @commands.command(name="rps", aliases=["rockpaperscissors"])
    async def rps(self, ctx: commands.Context, choice: str):
        """Play Rock Paper Scissors against the bot."""
        choices = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        choice = choice.lower()
        if choice not in choices:
            return await ctx.send("❌ Choose: `rock`, `paper`, or `scissors`")

        bot_choice = random.choice(list(choices.keys()))
        wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

        result = (
            "🏆 **You Win!**" if wins[choice] == bot_choice
            else ("😐 **It's a Tie!**" if choice == bot_choice else "😢 **You Lose!**")
        )
        embed = discord.Embed(title="✂️ Rock Paper Scissors", color=COLOR_PRIMARY)
        embed.add_field(name="Your Choice", value=choices[choice], inline=True)
        embed.add_field(name="Bot's Choice", value=choices[bot_choice], inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        await ctx.send(embed=embed)

    # ── !guess ────────────────────────────────────────────────────────────────

    @commands.command(name="guess", aliases=["guessnumber", "gn"])
    async def guessnumber(self, ctx: commands.Context, max_num: int = 100):
        """Guess a number between 1 and max_num (default 100)."""
        if ctx.channel.id in self.active_games:
            return await ctx.send("❌ A game is already running in this channel!")
        self.active_games.add(ctx.channel.id)

        number = random.randint(1, max_num)
        attempts = 0
        max_attempts = 8

        embed = discord.Embed(
            title="🔢 Number Guessing Game",
            description=f"I'm thinking of a number between **1** and **{max_num}**.\nYou have **{max_attempts}** attempts!",
            color=COLOR_PRIMARY,
        )
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            while attempts < max_attempts:
                guess_msg = await self.bot.wait_for("message", timeout=30.0, check=check)
                guess = int(guess_msg.content)
                attempts += 1

                if guess == number:
                    embed = discord.Embed(
                        title="🎉 Correct!",
                        description=f"You guessed **{number}** in **{attempts}** attempt(s)!",
                        color=COLOR_SUCCESS,
                    )
                    return await ctx.send(embed=embed)
                elif guess < number:
                    await ctx.send(f"📈 Too low! ({max_attempts - attempts} attempts left)")
                else:
                    await ctx.send(f"📉 Too high! ({max_attempts - attempts} attempts left)")

            await ctx.send(f"❌ Out of attempts! The number was **{number}**.")
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! The number was **{number}**.")
        finally:
            self.active_games.discard(ctx.channel.id)

    # ── !hangman ──────────────────────────────────────────────────────────────

    @commands.command(name="hangman", aliases=["hm"])
    async def hangman(self, ctx: commands.Context):
        """Play a game of Hangman!"""
        if ctx.channel.id in self.active_games:
            return await ctx.send("❌ A game is already running in this channel!")
        self.active_games.add(ctx.channel.id)

        word = random.choice(HANGMAN_WORDS)
        guessed: set[str] = set()
        wrong = 0

        def display_word():
            return " ".join(c if c in guessed else "\_" for c in word)

        def make_embed():
            embed = discord.Embed(title="🎯 Hangman", color=COLOR_PRIMARY)
            embed.add_field(name="Progress", value=f"`{display_word()}`", inline=False)
            embed.add_field(name="Wrong Guesses", value=f"{wrong}/6 — {', '.join(guessed - set(word)) or 'None'}", inline=False)
            embed.add_field(name="Gallows", value=HANGMAN_STAGES[wrong], inline=False)
            return embed

        await ctx.send(embed=make_embed())

        def check(m):
            return (
                m.author == ctx.author and
                m.channel == ctx.channel and
                len(m.content) == 1 and
                m.content.isalpha()
            )

        try:
            while wrong < 6 and not all(c in guessed for c in word):
                guess_msg = await self.bot.wait_for("message", timeout=30.0, check=check)
                letter = guess_msg.content.lower()
                if letter in guessed:
                    await ctx.send(f"⚠️ Already guessed `{letter}`!", delete_after=3)
                    continue
                guessed.add(letter)
                if letter not in word:
                    wrong += 1
                await ctx.send(embed=make_embed())

            if all(c in guessed for c in word):
                await ctx.send(f"🎉 **You won!** The word was **{word.upper()}**!")
            else:
                await ctx.send(f"💀 **You lost!** The word was **{word.upper()}**.")
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! The word was **{word.upper()}**.")
        finally:
            self.active_games.discard(ctx.channel.id)

    # ── !slots ────────────────────────────────────────────────────────────────

    @commands.command(name="slots")
    async def slots(self, ctx: commands.Context):
        """Spin the slot machine!"""
        symbols = ["🍎", "🍋", "🍇", "🔔", "💎", "⭐", "🎰"]
        result = [random.choice(symbols) for _ in range(3)]
        msg = await ctx.send("🎰 Spinning...")
        await asyncio.sleep(1)
        display = f"| {' | '.join(result)} |"
        if result[0] == result[1] == result[2]:
            embed = discord.Embed(
                title="🎰 JACKPOT!",
                description=f"**{display}**\n\n🎉 All three match! You win BIG!",
                color=COLOR_SUCCESS,
            )
        elif result[0] == result[1] or result[1] == result[2]:
            embed = discord.Embed(
                title="🎰 Small Win!",
                description=f"**{display}**\n\nTwo match — small win!",
                color=COLOR_PRIMARY,
            )
        else:
            embed = discord.Embed(
                title="🎰 No Match",
                description=f"**{display}**\n\nBetter luck next time!",
                color=COLOR_ERROR,
            )
        await msg.edit(content=None, embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
