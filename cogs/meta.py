import discord
from discord.ext import commands

import asyncio

import datetime
import traceback
import os
import json
import sys
import humanize

def has_manage_guild():
    async def predicate(ctx):
        try:
            await commands.has_guild_permissions(manage_guild=True).predicate(ctx)
            permissions = True
        except commands.errors.MissingPermissions:
            permissions = False
        return (
            ctx.author.id == ctx.bot.owner_id
            or permissions
        )
    return commands.check(predicate)

class RoboCoderHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{bot.user.name} Help", description="Help for Robo Coder Bot. Use `help [command]` or `help [Category]` for more specific help.\n", color=0x96c8da)
        msg = ""
        for name, cog in sorted(bot.cogs.items()):
            if not getattr(cog, "hidden", False):
                msg += f"\n{getattr(cog, 'emoji', '')} {cog.qualified_name}"
        em.add_field(name="Categories", value=msg)
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)
        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{getattr(cog, 'emoji', '')} {cog.qualified_name}", description="\n", color=0x96c8da)
        commands = await self.filter_commands(cog.get_commands())
        for command in commands:
            if not command.hidden:
                em.description += f"{self.get_command_signature(command)} {'-' if command.description else ''} {command.description}\n"

        em.description += "\nKey: <required> [optional]. Remove <> and [] when using the command."
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{command.name} {command.signature}", description=command.description or "", color=0x96c8da)
        if command.aliases:
            em.description += f"\nAliases: {', '.join(command.aliases)}"
        em.description += "\nKey: <required> [optional]. Remove <> and [] when using the command."
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{group.name} {group.signature}", description=group.description or "", color=0x96c8da)
        if group.aliases:
            em.description += f"\nAliases: {', '.join(group.aliases)} \n"

        commands = await self.filter_commands(group.commands)
        for command in commands:
            em.description += f"\n{self.get_command_signature(command)} {'-' if command.description else ''} {command.description}"

        em.description += "\nKey: <required> [optional]. Remove <> and [] when using the command."
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

class Meta(commands.Cog):
    """Everything about the bot itself."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":gear:"

        self._original_help_command = bot.help_command
        bot.help_command = RoboCoderHelpCommand()
        bot.help_command.cog = self

        if os.path.exists("prefixes.json"):
            with open("prefixes.json", "r") as f:
                self.bot.guild_prefixes = json.load(f)
        else:
            self.bot.guild_prefixes = {}

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.Cog.listener("on_command_error")
    async def _send_error(self, ctx, e: commands.CommandError):
        error = "".join(traceback.format_exception(type(e), e, e.__traceback__, 1))
        print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
        
        if isinstance(e, discord.ext.commands.NoPrivateMessage):
            return await ctx.send("This command can not be used in DMs")
        elif isinstance(e, discord.ext.commands.errors.BotMissingPermissions):
            perms_text = "\n".join([f"- {perm.replace('_', ' ').capitalize()}" for perm in e.missing_perms])
            return await ctx.send(f":x: I am missing some permissions:\n {perms_text}") 
        elif isinstance(e, discord.ext.commands.errors.CheckFailure):
            return
        elif isinstance(e, discord.ext.commands.errors.MissingRequiredArgument):
            return await ctx.send(f":x: You are missing a argument: `{e.param}`")
        elif isinstance(e, discord.ext.commands.errors.BadArgument):
            return await ctx.send(f":x: {e}")
        elif isinstance(e, discord.ext.commands.MaxConcurrencyReached):
            if e.per == commands.BucketType.default:
                return await ctx.send(f":x: This command can only be used {e.number} time(s) on the bot at once")
            if e.per == commands.BucketType.user:
                return await ctx.send(f":x: You can only use this command {e.number} time(s) per at once")
            if e.per == commands.BucketType.guild:
                return await ctx.send(f":x: This command can only be used {e.number} time(s) per server at once")
            if e.per == commands.BucketType.channel:
                return await ctx.send(f":x: This command can only be used {e.number} time(s) per channel at once")
            if e.per == commands.BucketType.member:
                return await ctx.send(f":x: You an only use this command {e.number} time(s) per member in the server at once")
            if e.per == commands.BucketType.category:
                return await ctx.send(f":x: You can only use this command {e.number} time(s) per category at once")
            if e.per == commands.BucketType.role:
                return await ctx.send(f":x: THis command can only be used {e.number} time(s) per role at once")

        elif isinstance(e, discord.ext.commands.errors.CommandOnCooldown):
            return await ctx.send(f"You are on cooldown. Try again in {e.retry_after} seconds")
        elif isinstance(e, discord.ext.commands.errors.CommandNotFound):
            return

        em = discord.Embed(title=":warning:",
                           color=0xff0000,
                           timestamp=datetime.datetime.utcnow())
        em.description = f"```py\n{str(e)}```\n"
        msg = await ctx.send(embed=em)

    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send("prefixes: " + ", ".join(self.bot.guild_prefixes[str(ctx.guild.id)]))

    @commands.command(name="hello", aliases=["hi"])
    async def hi(self, ctx):
        await ctx.send(f":wave: Hello, I am Robo Coder!\nTo get more info use {ctx.prefix}help")

    @prefix.command(name="add", description="add a prefix")
    @commands.guild_only()
    @has_manage_guild()
    async def add(self, ctx, *, arg):
        self.bot.guild_prefixes[str(ctx.guild.id)].append(arg)
        with open("prefixes.json", "w") as f:
            json.dump(self.bot.guild_prefixes, f)
        await ctx.send("Added prefix: " + arg)
    
    @prefix.command(name="remove", description="remove prefix")
    @commands.guild_only()
    @has_manage_guild()
    async def remove(self, ctx, *, arg):
        if arg in self.bot.guild_prefixes[str(ctx.guild.id)]:
            self.bot.guild_prefixes[str(ctx.guild.id)].remove(arg)
            await ctx.send("Removed prefix: " + arg)
        else:
            await ctx.send(f"That prefix does not exist. Try '{ctx.prefix}prefixes' to get a list of prefixes")

        with open("prefixes.json", "w") as f:
            json.dump(self.bot.guild_prefixes, f)

    @prefix.command(name="prefixes", description="veiw a list of prefixes")
    @commands.guild_only()
    async def prefixes(self, ctx):
        server_prefixes = self.bot.guild_prefixes
        await ctx.send("prefixes: " + ", ".join(server_prefixes))        

    @commands.command(name="ping", description="Check my latency")
    async def ping(self, ctx):
        await ctx.send(f"My latency is {int(self.bot.latency*1000)}ms")

    @commands.group(name="uptime", description="Get the uptime", aliases=["up"], invoke_without_command=True)
    async def uptime(self, ctx):
        uptime = datetime.datetime.utcnow()-self.bot.startup_time
        await ctx.send(f"I started up {humanize.naturaldelta(uptime)} ago")
    
    @commands.command(name="invite", description="Get a invite to add me to your server")
    async def invite(self, ctx):
        perms  = discord.Permissions.none()
        perms.manage_messages = True
        perms.kick_members = True
        perms.ban_members = True
        perms.manage_channels = True
        perms.manage_roles = True
        perms.manage_webhooks = True
        invite = discord.utils.oauth_url(self.bot.user.id, permissions=perms, guild=None, redirect_uri=None)
        await ctx.send(f"<{invite}>")

def setup(bot):
    bot.add_cog(Meta(bot))
