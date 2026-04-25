"""
error_handler.py — Global error handling and structured logging.
"""

import traceback
import discord
from discord.ext import commands
from config.settings import COLOR_ERROR
import logging

log = logging.getLogger("bot")


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle prefix command errors."""

        # Ignored error types
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                color=COLOR_ERROR,
            )
            return await ctx.send(embed=embed, delete_after=10)

        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(title="❌ Bad Argument", description=str(error), color=COLOR_ERROR)
            return await ctx.send(embed=embed, delete_after=10)

        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions).replace("_", " ").title()
            embed = discord.Embed(
                title="🚫 Missing Permissions",
                description=f"You need: **{perms}**",
                color=COLOR_ERROR,
            )
            return await ctx.send(embed=embed, delete_after=10)

        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions).replace("_", " ").title()
            embed = discord.Embed(
                title="🚫 Bot Missing Permissions",
                description=f"I need: **{perms}**",
                color=COLOR_ERROR,
            )
            return await ctx.send(embed=embed, delete_after=10)

        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"Try again in **{error.retry_after:.1f}s**",
                color=COLOR_ERROR,
            )
            return await ctx.send(embed=embed, delete_after=5)

        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="You do not have permission to use this command.",
                color=COLOR_ERROR,
            )
            return await ctx.send(embed=embed, delete_after=5)

        # Unknown errors — log them
        log.error("Unhandled command error in %s: %s", ctx.command, error)
        log.error(traceback.format_exc())
        embed = discord.Embed(
            title="💥 Unexpected Error",
            description=f"```{str(error)[:1000]}```",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handle slash command errors."""
        msg = str(error)
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "You don't have permission to use this command."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"Cooldown! Try again in {error.retry_after:.1f}s."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            msg = "I'm missing required permissions."

        embed = discord.Embed(title="❌ Error", description=msg, color=COLOR_ERROR)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
