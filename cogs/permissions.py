import discord
from discord.ext import commands
import json
import os

PERMS_FILE = "data/permissions.json"

def load_perms():
    if not os.path.exists(PERMS_FILE):
        return {}
    with open(PERMS_FILE, "r") as f:
        return json.load(f)

def save_perms(data):
    with open(PERMS_FILE, "w") as f:
        json.dump(data, f, indent=4)

class Permissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.perms = load_perms()

        # Add global check
        self.bot.add_check(self.global_permission_check)

    def cog_unload(self):
        self.bot.remove_check(self.global_permission_check)

    async def global_permission_check(self, ctx):
        if await self.bot.is_owner(ctx.author):
            return True # Owner bypasses all restrictions
            
        if not ctx.command:
            return True

        command_name = ctx.command.qualified_name
        
        # Check if the command is restricted
        if command_name in self.perms and self.perms[command_name].get("restricted", False):
            # Check if user is explicitly allowed
            allowed_users = self.perms[command_name].get("allowed_users", [])
            if ctx.author.id not in allowed_users:
                await ctx.send(f"🚫 You do not have permission to use the `{command_name}` command.")
                return False
                
        return True

    @commands.group(invoke_without_command=True)
    @commands.is_owner()
    async def perms(self, ctx):
        """Manage command permissions. Subcommands: restrict, unrestrict, grant, revoke."""
        await ctx.send_help(ctx.command)

    @perms.command()
    @commands.is_owner()
    async def restrict(self, ctx, command_name: str):
        """Restricts a command so only allowed users can use it."""
        if not self.bot.get_command(command_name):
            return await ctx.send(f"❌ Command `{command_name}` not found.")
            
        if command_name not in self.perms:
            self.perms[command_name] = {"restricted": True, "allowed_users": []}
        else:
            self.perms[command_name]["restricted"] = True
            
        save_perms(self.perms)
        await ctx.send(f"🔒 Command `{command_name}` is now restricted. Only allowed users can use it.")

    @perms.command()
    @commands.is_owner()
    async def unrestrict(self, ctx, command_name: str):
        """Removes restriction from a command."""
        if command_name in self.perms:
            self.perms[command_name]["restricted"] = False
            save_perms(self.perms)
        await ctx.send(f"🔓 Command `{command_name}` is now public.")

    @perms.command()
    @commands.is_owner()
    async def grant(self, ctx, command_name: str, member: discord.Member):
        """Grants a specific user access to a restricted command."""
        if command_name not in self.perms:
            self.perms[command_name] = {"restricted": True, "allowed_users": []}
            
        if member.id not in self.perms[command_name].get("allowed_users", []):
            self.perms[command_name].setdefault("allowed_users", []).append(member.id)
            save_perms(self.perms)
            
        await ctx.send(f"✅ Granted {member.mention} access to use `{command_name}`.")

    @perms.command()
    @commands.is_owner()
    async def revoke(self, ctx, command_name: str, member: discord.Member):
        """Revokes a user's access to a restricted command."""
        if command_name in self.perms:
            if member.id in self.perms[command_name].get("allowed_users", []):
                self.perms[command_name]["allowed_users"].remove(member.id)
                save_perms(self.perms)
        await ctx.send(f"❌ Revoked {member.mention}'s access to `{command_name}`.")

async def setup(bot):
    await bot.add_cog(Permissions(bot))
