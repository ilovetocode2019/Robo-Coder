import discord
from discord.ext import commands

import re

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji  = ":label:"

    @commands.group(name="rolecolor", description="Assign yourself a role color", invoke_without_command=True)
    async def rolecolor(self, ctx, *, color: discord.Color = None):
        moderation = self.bot.get_cog("Moderation")
        if not moderation:
            return await ctx.end(":x: This feature is temporarily unavailable")
        config = await moderation.get_guild_config(ctx.guild)

        if not config.role_colors:
            return await ctx.send(":x: Role colors are not enabled")

        regex = re.compile("^#\w{1,6} color$")
        for role in ctx.author.roles:
            if regex.search(role.name):
                await ctx.author.remove_roles(role)

        if not color:
            return await ctx.send(":white_check_mark: Removed your role color")

        role = discord.utils.get(ctx.guild.roles, name=f"{color} color")
        if not role:
            role = await ctx.guild.create_role(name=f"{color} color", color=color)

        await ctx.author.add_roles(role)
        await ctx.send(f":white_check_mark: Your role color is now {color}")

    @rolecolor.command(name="enable", description="Enable role colors")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rolecolor_enable(self, ctx):
        moderation = self.bot.get_cog("Moderation")
        if not moderation:
            return await ctx.end(":x: This feature is temporarily unavailable")
        config = await moderation.get_guild_config(ctx.guild)

        if config.role_colors:
            return await ctx.send(":x: Role colors are already enabled")

        await config.enable_role_colors()
        await ctx.send(":white_check_mark: Role colors are now enabled")

    @rolecolor.command(name="disable", description="Disable role colors")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rolecolor_disable(self, ctx):
        moderation = self.bot.get_cog("Moderation")
        if not moderation:
            return await ctx.end(":x: This feature is temporarily unavailable")
        config = await moderation.get_guild_config(ctx.guild)

        if not config.role_colors:
            return await ctx.send(":x: Role colors are already disabled")

        await config.disable_role_colors()
        await ctx.send(":white_check_mark: Role colors are now disabled")

def setup(bot):
    bot.add_cog(Roles(bot))
