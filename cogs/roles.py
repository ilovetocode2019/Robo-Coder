import discord
from discord.ext import commands

import re
import asyncpg
import collections
import asyncio
import functools
import inspect

class LRUDict(collections.OrderedDict):
    def __init__(self, max_legnth = 10, *args, **kwargs):
        if max_legnth <= 0:
            raise ValueError()
        self.max_legnth = max_legnth

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)

        if len(self) > 10:
            super().__delitem__(list(self)[0])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

def cache(max_legnth = 100):
    def decorator(func):
        cache = LRUDict(max_legnth=max_legnth)

        def __len__():
            return len(cache)

        def _get_key(*args, **kwargs):
            return f"{':'.join([repr(arg) for arg in args])}{':'.join([f'{repr(kwarg)}={repr(value)}' for kwarg, value in kwargs.items()])}"

        def invalidate(*args, **kwargs):
            if not args:
                cache.clear()
                return

            try:
                key = _get_key(*args, **kwargs)
                del cache[key]
                return True
            except KeyError:
                return False

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            key = _get_key(*args, **kwargs)

            try:
                value = cache[key]
                if asyncio.iscoroutinefunction(func):
                    async def coro():
                        return value
                    return coro()
                return value

            except KeyError:
                value = func(*args, **kwargs)
                if inspect.isawaitable(value):
                    async def coro():
                        result = await value
                        cache[key] = result
                        return result
                    return coro()

                cache[key] = value
                return value


        wrapped.invalidate = invalidate
        wrapped.cache = cache
        wrapped._get_key = _get_key
        wrapped.__len__ = __len__
        return wrapped

    return decorator

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

        await ctx.send(":white_check_mark: Added role to autorole list")

    @cache()
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
