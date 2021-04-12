import discord
from discord.ext import commands

import asyncio

import os
import sys
import traceback

from .utils import errors, formats, human_time, menus

class Prefix(commands.Converter):
    async def convert(self, ctx, prefix):
        if discord.utils.escape_mentions(prefix) != prefix:
            raise commands.BadArgument("Prefix can't include a mention")
        return prefix

class RoboCoderHelpCommand(commands.HelpCommand):
    bottom_text = "\n\nKey: `<required> [optional]`. **Remove <> and [] when using the command**. \nFor more help join the [support server]({0})."

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(
            title=f"{bot.user.name} Help",
            description=f"{bot.description}. Use `{self.clean_prefix}help [command]` or `{self.clean_prefix}help [Category]` for more specific help. If you need more help you can join the [support server]({bot.support_server_link}).",
            color=0x96c8da
            )

        message = ""
        for name, cog in sorted(bot.cogs.items()):
            if not getattr(cog, "hidden", False):
                message += f"\n{getattr(cog, 'emoji', '')} {cog.qualified_name}"
        em.add_field(name="Categories", value=message)
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)
        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{getattr(cog, 'emoji', '')} {cog.qualified_name}", description="\n", color=0x96c8da)
        commands = await self.filter_commands(cog.walk_commands())
        for command in commands:
            em.description += f"\n`{self.get_command_signature(command).strip()}` {'-' if command.description else ''} {command.description}"

        em.description += self.bottom_text.format(bot.support_server_link)
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{command.name} {command.signature.strip()}", description=command.description or "", color=0x96c8da)
        if command.aliases:
            em.description += f"\nAliases: {', '.join(command.aliases)}"
        em.description += self.bottom_text.format(bot.support_server_link)
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{group.name} {group.signature.strip()}", description=group.description or "", color=0x96c8da)
        if group.aliases:
            em.description += f"\nAliases: {', '.join(group.aliases)} \n"

        commands = await self.filter_commands(group.commands)
        for command in commands:
            em.description += f"\n`{self.get_command_signature(command).strip()}` {'-' if command.description else ''} {command.description}"

        em.description += self.bottom_text.format(bot.support_server_link)
        em.set_footer(text=bot.user.name, icon_url=bot.user.avatar_url)

        await ctx.send(embed=em)

class Meta(commands.Cog):
    """Stuff related to the bot itself."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":gear:"

        self._original_help_command = bot.help_command
        bot.help_command = RoboCoderHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("This command can only be used in DMs")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in DMs")
        elif isinstance(error, commands.errors.BotMissingPermissions):
            perms_text = "\n".join([f"- {perm.replace('_', ' ').capitalize()}" for perm in error.missing_perms])
            await ctx.send(f":x: I am missing some permissions:\n {perms_text}") 
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send(f":x: You are missing a required argument: `{error.param.name}`")
        elif isinstance(error, commands.UserInputError):
            await ctx.send(f":x: {error}")
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(f":x: {error}")
        elif isinstance(error, commands.errors.CommandOnCooldown):
            await ctx.send(f"You are on cooldown. Try again in {formats.plural(int(error.retry_after)):second}.")
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(f":x: {error}")

        if isinstance(error, errors.SongError):
            await ctx.send(f":x: {error}")
        elif isinstance(error, errors.VoiceError) and str(error):
            await ctx.send(f":x: {error}")

        if isinstance(error, commands.CommandInvokeError):
            em = discord.Embed(
                title=":warning: Error",
                description=f"An unexpected error has occured. If you're confused or think this is a bug you can join the [support server]({self.bot.support_server_link}). \n```py\n{error}```",
                color=discord.Color.gold()
            )
            em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=em)

            em = discord.Embed(title=":warning: Error", description="", color=discord.Color.gold())
            em.description += f"\nCommand: `{ctx.command}`"
            em.description += f"\nLink: [Jump]({ctx.message.jump_url})"
            em.description += f"\n\n```py\n{error}```\n"

            await self.bot.console.send(embed=em)

    @commands.command(name="hello", description="Say hello", aliases=["hi"])
    async def hi(self, ctx):
        await ctx.send(f":wave: Hello, I am Robo Coder!\nTo get more info use {ctx.prefix}help")

    @commands.command(name="ping", description="Check my latency")
    async def ping(self, ctx):
        await ctx.send(f"My latency is {int(self.bot.latency*1000)}ms")

    @commands.group(name="uptime", description="Get the uptime", aliases=["up"], invoke_without_command=True)
    async def uptime(self, ctx):
        await ctx.send(f"I started up {human_time.timedelta(self.bot.uptime, accuracy=None)}")

    @commands.command(name="invite", description="Get a link to add me to your server")
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

    @commands.command(name="support", description="Get an invite link for my support server")
    async def support(self, ctx):
        await ctx.send(self.bot.support_server_link)

    @commands.command(name="code", description="Find out what I'm made of")
    async def code(self, ctx):
        file_count = 0
        line_count = 0
        comment_count = 0
        class_count = 0
        function_count = 0

        for root, directories, files in os.walk("."):
            if "venv" in directories:
                directories.remove("venv")

            for filename in files:
                if filename.endswith(".py"):
                    path = os.path.join(root, filename)
                    file_count += 1

                    with open(path, encoding="utf-8") as file:
                        for counter, line in enumerate(file):
                            line = line.strip()
                            line_count += 1

                            if line.startswith("#"):
                                comment_count += 1
                            elif line.startswith("class"):
                                class_count += 1
                            elif line.startswith("def"):
                                function_count += 1

        em = discord.Embed(title="Code", description=f"I am made of {line_count} of python code, spread across {file_count} files", color=0x96c8da)
        em.add_field(name="Files", value=file_count)
        em.add_field(name="Lines", value=line_count)
        em.add_field(name="Comments", value=comment_count)
        em.add_field(name="Classes", value=class_count)
        em.add_field(name="Functions", value=function_count)
        await ctx.send(embed=em)

    @commands.group(name="prefix", description="Manage custom prefixes", invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send_help(ctx.command)

    @prefix.command(name="add", description="Add a prefix")
    @commands.has_permissions(manage_guild=True)
    async def prefix_add(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild)
        if prefix in prefixes:
            return await ctx.send(":x: That prefix is already added")

        if len(prefixes) > 10:
            return await ctx.send(":x: You cannot have more than 10 custom prefixes")

        prefixes.append(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f":white_check_mark: Added the prefix `{prefix}`")

    @prefix.command(name="remove", description="Remove a prefix")
    @commands.has_permissions(manage_guild=True)
    async def prefix_remove(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild)
        if prefix not in prefixes:
            return await ctx.send(":x: That prefix is not added")

        prefixes.remove(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f":white_check_mark: Removed the prefix `{prefix}`")

    @prefix.command(name="default", description="Set a prefix as the first prefix")
    @commands.has_permissions(manage_guild=True)
    async def prefix_default(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild)
        if prefix in prefixes:
            prefixes.remove(prefix)

        if len(prefixes) >= 10:
            return await ctx.send(":x: You cannot have more than 10 prefixes")

        prefixes = [prefix] + prefixes
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f":white_check_mark: Set `{prefix}` as the default prefix")

    @prefix.command(name="clear", description="Clear all the prefixes in this server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_clear(self, ctx):
        result = await menus.Confirm("Are you sure you want to clear all your prefixes?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await self.bot.prefixes.add(ctx.guild.id, [])
        await ctx.send(f":white_check_mark: Removed all prefixes")

    @prefix.command(name="reset", description="Reset the prefixes to the default prefixes")
    @commands.has_permissions(manage_guild=True)
    async def prefix_reset(self, ctx):
        result = await menus.Confirm("Are you sure you want to clear all your prefixes?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await self.bot.prefixes.add(ctx.guild.id, ["r!", "r."])
        await ctx.send(f":white_check_mark: Reset prefixes")

    @prefix.command(name="list", description="View the prefixes in this server")
    async def prefix_list(self, ctx):
        prefixes = await self.bot.get_prefix(ctx.message)
        prefixes.pop(0)

        em = discord.Embed(title="Prefixes", description="\n".join(prefixes), color=0x96c8da)
        em.set_footer(text=f"{formats.plural(len(prefixes), end='es'):prefix}")
        await ctx.send(embed=em)

    @commands.command(name="prefixes", description="View the prefixes in this server")
    async def prefixes(self, ctx):
        await ctx.invoke(self.prefix_list)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content == f"<@!{self.bot.user.id}>" and not message.author.bot:
            prefix = self.bot.get_guild_prefix(message.guild)
            await message.channel.send(f":wave: Hello, I am Robo Coder!\nTo get more info use {prefix}help")

def setup(bot):
    bot.add_cog(Meta(bot))
