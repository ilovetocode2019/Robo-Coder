from discord.ext import commands
from discord.ext import tasks
from discord.ext import menus
import discord

import asyncio

from datetime import datetime
import traceback
import os
from datetime import datetime as d
import random
import pickle
import json
import sys
import importlib
import inspect

from .utils import time
from .utils import custom
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

async def run_command_checks(checks, ctx):
    try:
        for check in checks:
            if inspect.iscoroutinefunction(check):
                if not await check(ctx):
                    return False
            else:
                if not check(ctx):
                    return False
        return True
    except:
        return False

async def run_cog_check(check, ctx):
    try:
        if inspect.iscoroutinefunction(check):
            if not await check(ctx):
                return False
        else:
            if not check(ctx):
                return False
        return True
    except:
        return False
class CogHelp(menus.ListPageSource):
    def __init__(self, data, ctx):
        self.cog = data
        self.bot = ctx.bot
        self.ctx = ctx
        super().__init__(data.get_commands(), per_page=12)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        
        guild_prefix = self.bot.get_cog("Meta").get_guild_prefix(self.ctx.guild)

        if not self.cog.description:
            cogdescription = ""
        else:
            cogdescription = self.cog.description
        em = self.bot.build_embed(title=self.cog.qualified_name, description=cogdescription+"\n")

        for i, command in enumerate(entries, start=offset):
            if command.hidden != True:
                if await run_command_checks(command.checks, self.ctx):
                    if not command.usage:
                        usage = ""
                    else:
                        usage = f"{command.usage}"

                    if not command.description:
                        description = "No desciption"
                    else:
                        description = command.description

                    if not command.aliases:
                        aliases = ""
                    else:
                        aliases = "("+', '.join(command.aliases)+")"

                    em.description += f"\n\n{guild_prefix}{command.name} {usage} - {description} {aliases}"

                    if isinstance(command, commands.Group):
                            for subcommand in command.commands:
                                if await run_command_checks(subcommand.checks, self.ctx):
                                    if not subcommand.usage:
                                        usage = ""
                                    else:
                                        usage = f"{subcommand.usage}"

                                    if not subcommand.description:
                                        description = "No desciption"
                                    else:
                                        description = subcommand.description

                                    if not subcommand.aliases:
                                        aliases = ""
                                    else:
                                        aliases = "("+', '.join(subcommand.aliases)+")"

                                    em.description += f"\n\n{guild_prefix}{command.name} {subcommand.name} {usage} - {description} {aliases}"


        em.set_footer(text = f"{self.bot.user.name}", icon_url=self.bot.user.avatar_url)
        return em


class RoboCoderHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        em = bot.build_embed(title=f"{bot.user.name} Help", description="Help for Robo Coder Bot. Use `help [command]` or `help [Category]` for more specific help.\n")
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

        if getattr(cog, "hidden", False):
           return 

        em = bot.build_embed(title=f"{getattr(cog, 'emoji', '')} {cog.qualified_name}", description="\n")
        for command in cog.get_commands():
            if not command.hidden:
                em.description += f"{self.get_command_signature(command)}\n"
        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        if not await command.can_run(ctx):
            return

        em = bot.build_embed(title=f"{bot.user.name} Help", description=self.get_command_signature(command))
        await ctx.send(embed=em)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        if not await group.can_run(ctx):
            return

        em = bot.build_embed(title=f"{bot.user.name} Help", description=f"\n{self.get_command_signature(group)}")
        for command in group.commands:
            if await command.can_run(ctx):
                em.description += f"\n{self.get_command_signature(command)}"

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
            with open("prefixes.json", "w") as f:
                data = {}
                json.dump(data, f)
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
                           timestamp=d.utcnow())
        em.description = f"```py\n{str(e)}```\n"
        msg = await ctx.send(embed=em)

    @commands.Cog.listener("on_message")
    async def detect_mention(self, msg):
        if msg.content == f"<@!{self.bot.user.id}>":
            await msg.channel.send(f"Hi. For help use {self.get_guild_prefix(msg.guild)}help.")

    def get_guild_prefix(self, guild):
        if not guild:
            return "r!"
        return self.bot.guild_prefixes[str(guild.id)][0]

    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send("prefixes: " + ", ".join(self.bot.guild_prefixes[str(ctx.guild.id)]))        


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
            await ctx.send(f"That prefix does not exist. Try '{self.get_guild_prefix(ctx.guild)}prefixes' to get a list of prefixes")

        with open("prefixes.json", "w") as f:
            json.dump(self.bot.guild_prefixes, f)

    @prefix.command(name="prefixes", description="veiw a list of prefixes")
    @commands.guild_only()
    async def prefixes(self, ctx):
        server_prefixes = self.bot.guild_prefixes
        await ctx.send("prefixes: " + ", ".join(server_prefixes))        

        
    @commands.command(name = "ping", description = "Test the bots's latency")
    async def ping(self, ctx):
        start = datetime.timestamp(ctx.message.created_at)
        msg = await ctx.send("Pinging")

        ping = round((datetime.timestamp(datetime.utcnow()) - start) * 1000, 2)
        await msg.edit(content=f"Pong!\nOne message round-trip took {ping}ms, my latency is {int(self.bot.latency*1000)}ms")

    async def get_overall_uptime(self):
        rows = await self.bot.db.fetch("SELECT * FROM status_updates WHERE status_updates.userid=$1", self.bot.user.id)
        status = {}
        for x, row in enumerate(rows):
            if len(rows) == x+1:
                time = datetime.timestamp(datetime.utcnow())-row[2]
            else:
                time = rows[x+1][2]-row[2]
            
            if row[1] in status:
                status[row[1]] += time
            else:
                status[row[1]] = time
        
        total = sum(status.values())
        return f"I am online {(status['online']/total)*100}% of the time"


    @commands.group(name="uptime", description="Get the uptime", aliases=["up"], invoke_without_command=True)
    async def uptime(self, ctx):
        uptime = datetime.now()-self.bot.startup_time
        await ctx.send(f"I started up {time.readable(uptime)} ago")  
    
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