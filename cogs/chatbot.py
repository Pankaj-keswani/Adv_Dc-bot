"""
chatbot.py — Advanced AI chatbot with per-user memory using Groq API.
"""
# NOTE: Requires groq>=0.12.0

import discord
from discord.ext import commands
from discord import app_commands
import groq
from collections import defaultdict
from config.settings import (
    GROQ_API_KEY, GROQ_MODEL, AI_MAX_TOKENS,
    AI_MEMORY_LIMIT, SYSTEM_PROMPT, COLOR_PRIMARY, COLOR_ERROR
)
from handlers.json_handler import get_guild_config
import logging

log = logging.getLogger("bot")


class Chatbot(commands.Cog):
    """Advanced AI chatbot with per-user conversation memory."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = None  # initialized in cog_load
        # {user_id: [{"role": "user"/"assistant", "content": "..."}]}
        self.memory: dict[int, list[dict]] = defaultdict(list)
        self.typing_guilds: set[int] = set()

    async def cog_load(self):
        """Initialize Groq client asynchronously."""
        self.client = groq.AsyncGroq(api_key=GROQ_API_KEY)

    def _build_messages(self, user_id: int, new_message: str) -> list[dict]:
        history = self.memory[user_id][-AI_MEMORY_LIMIT:]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": new_message},
        ]

    async def _ask_groq(self, user_id: int, message: str) -> str:
        messages = self._build_messages(user_id, message)
        try:
            response = await self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=AI_MAX_TOKENS,
                temperature=0.75,
            )
            reply = response.choices[0].message.content.strip()
            # Update memory
            self.memory[user_id].append({"role": "user", "content": message})
            self.memory[user_id].append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            log.error("Groq API error: %s", e)
            return f"⚠️ AI error: `{e}`"

    # ── Slash: /chat ──────────────────────────────────────────────────────────

    @app_commands.command(name="chat", description="Chat with the AI bot (remembers context)")
    @app_commands.describe(message="Your message to the AI")
    async def chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(thinking=True)
        reply = await self._ask_groq(interaction.user.id, message)
        embed = discord.Embed(description=reply, color=COLOR_PRIMARY)
        embed.set_author(name=f"Replying to {interaction.user.display_name}",
                         icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="🧠 AI has memory of this conversation • /forget to reset")
        await interaction.followup.send(embed=embed)

    # ── Slash: /forget ────────────────────────────────────────────────────────

    @app_commands.command(name="forget", description="Clear the AI's memory of your conversation")
    async def forget(self, interaction: discord.Interaction):
        self.memory.pop(interaction.user.id, None)
        embed = discord.Embed(
            title="🧹 Memory Cleared",
            description="I've forgotten our conversation. Fresh start!",
            color=COLOR_PRIMARY,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Slash: /setaichannel ──────────────────────────────────────────────────

    @app_commands.command(name="setaichannel", description="Set the AI auto-chat channel")
    @app_commands.describe(channel="Channel where all messages will be AI-replied")
    @app_commands.default_permissions(administrator=True)
    async def setaichannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from handlers.json_handler import update_guild_key
        await update_guild_key(interaction.guild_id, "ai_channel", str(channel.id))
        embed = discord.Embed(
            title="✅ AI Channel Set",
            description=f"All messages in {channel.mention} will now be answered by AI.",
            color=COLOR_PRIMARY,
        )
        await interaction.response.send_message(embed=embed)

    # ── Auto-reply in AI channel ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = get_guild_config(message.guild.id)
        ai_ch = cfg.get("ai_channel")

        # Respond if message is in the dedicated AI channel OR bot is mentioned
        should_reply = (
            (ai_ch and str(message.channel.id) == str(ai_ch)) or
            (self.bot.user in message.mentions)
        )
        if not should_reply:
            return

        content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
        if not content:
            return

        async with message.channel.typing():
            reply = await self._ask_groq(message.author.id, content)

        # Split long replies
        chunks = [reply[i:i+1990] for i in range(0, len(reply), 1990)]
        for chunk in chunks:
            await message.reply(chunk)

    # ── Prefix: !chat ─────────────────────────────────────────────────────────

    @commands.command(name="chat", aliases=["ask", "ai"])
    async def chat_prefix(self, ctx: commands.Context, *, message: str):
        """Chat with the AI using prefix command."""
        async with ctx.typing():
            reply = await self._ask_groq(ctx.author.id, message)
        embed = discord.Embed(description=reply, color=COLOR_PRIMARY)
        embed.set_footer(text="🧠 Use !forget to clear memory")
        await ctx.reply(embed=embed)

    @commands.command(name="forget", aliases=["clearmemory"])
    async def forget_prefix(self, ctx: commands.Context):
        """Clear AI memory."""
        self.memory.pop(ctx.author.id, None)
        await ctx.send("🧹 Memory cleared!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Chatbot(bot))
