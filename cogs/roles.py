import discord
from discord.ext import commands

import asyncpg

from .utils import cache

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji  = ":label:"

    @commands.group(name="autorole", description="Automaticly assign roles to users with they join", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole(self, ctx):
        await ctx.send_help(ctx.command)

    @autorole.command(name="add", description="Add a role to the autorole list")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_add(self, ctx, *, role: discord.Role):
        if role.is_default() or role.managed:
            return await ctx.send(":x: You can't use this role as an autorole")
    
        query = """INSERT INTO autoroles (guild_id, role_id)
                   VALUES ($1, $2)
                """
        try:
            await self.bot.db.execute(query, ctx.guild.id, role.id)
        except asyncpg.UniqueViolationError:
            return await ctx.send(":x: This role is already in the autorole list")

        self.get_autoroles.invalidate(role.guild.id)

        await ctx.send(":white_check_mark: Added role to autorole list")

    @autorole.command(name="remove", description="Remove a role from the autorole list")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx, *, role: discord.Role):
        query = """DELETE FROM autoroles
                   WHERE autoroles.role_id=$1
                """
        result = await self.bot.db.execute(query, role.id)

        if result == "DELETE 0":
            return await ctx.send(":x: That role is not in the autorole list")

        self.get_autoroles.invalidate(role.guild.id)

        await ctx.send(":white_check_mark: Removed role from autorole list")

    @cache.cache()
    async def get_autoroles(self, guild):
        query = """SELECT *
                   FROM autoroles
                   WHERE autoroles.guild_id=$1;
                """
        autoroles = await self.bot.db.fetch(query, guild.id)
        return [guild.get_role(auto_role["role_id"]) for auto_role in autoroles]

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if await self.get_autoroles(role.guild):
            query = """DELETE FROM autoroles
                       WHERE autoroles.role_id=$1;
                    """
            await self.bot.db.execute(query, role.id)
            self.get_autoroles.invalidate(role.guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        roles = await self.get_autoroles(member.guild)
        await member.add_roles(*(role for role in roles if role))

def setup(bot):
    bot.add_cog(Roles(bot))
