import discord
from discord import app_commands
from discord.ext import commands

import os
import sys
import traceback

from .utils import errors, formats, human_time, menus


class PrefixConverter(commands.Converter):
    async def convert(self, ctx, prefix):
        if discord.utils.escape_mentions(prefix) != prefix:
            raise commands.BadArgument("Prefix can't include a mention")
        return prefix


class RoboCoderHelpCommand(commands.HelpCommand):
    bottom_text = "Usage: <required argument> [optional argument]. Remove brackets when using the command."

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        cogs = {command.cog.qualified_name: command.cog for command in await self.filter_commands(bot.commands) if hasattr(command.cog, "emoji")}
        lines = [f"{cog.emoji} {name}" for name, cog in sorted(cogs.items())]

        em = discord.Embed(
            title="Help",
            description=f"{bot.description}\n\nFor more specific help, use `{ctx.clean_prefix}help [command]` or `{ctx.clean_prefix}help [Category]`. Feel free to [join the support server]({bot.support_server_invite}) if you have questions.",
            color=0x96c8da
        )
        em.add_field(name="Categories", value="\n".join(lines))
        em.set_footer(text=self.bottom_text)

        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot
        commands = await self.filter_commands(cog.walk_commands())

        em = discord.Embed(
            title=f"Category: {cog.qualified_name}",
            description=f"**{cog.description}**\n" if len(cog.description) > 0 else "",
            color=0x96c8da
        )
        em.set_footer(text=self.bottom_text)

        for command in commands:
            em.description += f"\n`{self.get_command_signature(command).strip()}` {"-" if command.description else ""} {command.description}"

        await ctx.send(embed=em)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot
        commands = await self.filter_commands(group.commands)

        em = discord.Embed(
            title=f"{group.name} {group.signature.strip()}",
            description=f"**{group.description}**\n" if len(group.description) > 0 else "",
            color=0x96c8da
        )
        em.set_footer(text=self.bottom_text)

        for command in commands:
            em.description += f"\n`{self.get_command_signature(command).strip()}` {"-" if command.description else ""} {command.description}"

        if len(group.aliases) > 0:
            em.add_field(name="Aliases", value = ", ".join(group.aliases))

        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(
            title=f"{command.name} {command.signature.strip()}",
            description=command.description,
            color=0x96c8da
        )
        em.set_footer(text=self.bottom_text)

        if len(command.aliases) > 0:
            em.add_field(name="Aliases", value = ", ".join(command.aliases))

        await ctx.send(embed=em)


class Meta(commands.Cog):
    """General commands related to the bot itself."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":gear:"

        self._original_help_command = bot.help_command
        self._original_tree_on_error = bot.tree.on_error

        bot.help_command = RoboCoderHelpCommand()
        bot.help_command.cog = self
        bot.tree.on_error = self.on_interaction_error

    async def cog_unload(self):
        self.bot.help_command = self._original_help_command
        self.bot.tree.on_error = self._original_tree_on_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.HybridCommandError):
            error = error.original

        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("This command can only be used in DMs.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in DMs.")
        elif isinstance(error, commands.BotMissingPermissions):
            perms_text = "\n".join([f"- {perm.replace('_', ' ').capitalize()}" for perm in error.missing_permissions], ephemeral=True)
            await ctx.send(f"I am missing some permissions:\n {perms_text}", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You are missing a required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send(error.errors[0])
        elif isinstance(error, commands.UserInputError):
            await ctx.send(error)
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(error)
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(error)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"You are on cooldown. Try again in {formats.plural(int(error.retry_after)):second}.", ephemeral=True)
        elif isinstance(error, commands.ConversionError):
            await ctx.send(f"Command failed while converting {error.converter.__name__}: `{error.original}`")

        if isinstance(error, errors.SongError):
            await ctx.send(error, ephemeral=True)
        elif isinstance(error, errors.VoiceError) and str(error):
            await ctx.send(error, ephemeral=True)

        if isinstance(error, app_commands.TransformerError):
            await ctx.send(error, ephemeral=True)
        elif isinstance(error, human_time.BadTimeTransform):
            await ctx.send(error, ephemeral=True)

        if isinstance(error, commands.CommandInvokeError):
            em = discord.Embed(
                title=":warning: Error",
                description=f"An unexpected error has occured. If you're confused or need help, feel free to [join the support server]({self.bot.support_server_invite}). \n```py\n{error}```",
                color=discord.Color.gold()
            )
            em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

            await ctx.send(embed=em)

            em = discord.Embed(title=":warning: Command Error", description="", color=discord.Color.gold())
            em.description += f"\nCommand: `{ctx.command}`"
            em.description += f"\nLink: [Jump]({ctx.message.jump_url})"
            em.description += f"\nMessage ID: `{ctx.message.id}`"
            em.description += f"\n\n```py\n{error}```\n"

            if self.bot.console:
                await self.bot.console.send(embed=em)
        elif isinstance(error, app_commands.CommandInvokeError):
            em = discord.Embed(
                title=":warning: Error",
                description=f"An unexpected error has occured. If you're confused or need help, feel free to [join the support server]({self.bot.support_server_invite}). \n```py\n{error}```",
                color=discord.Color.gold()
            )
            em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

            message = await ctx.send(embed=em)

            em = discord.Embed(title=":warning: App Command Error", description="", color=discord.Color.gold())
            em.description += f"\nCommand: `{ctx.command}`"
            em.description += f"\nLink: [Jump]({ctx.message.jump_url})"
            em.description += f"\nMessage ID: `{ctx.message.id}`"
            em.description += f"\n\n```py\n{error}```\n"

            if self.bot.console:
                await self.bot.console.send(embed=em)

    async def on_interaction_error(self, interaction, error):
        if interaction.command is not None:
            ctx = await self.bot.get_context(interaction)
            await self.on_command_error(ctx, error)

    @commands.command(description="Provides general information about me", aliases=["hello", "hi"])
    async def about(self, ctx):
        message = (
            "Hey, I'm Robo Coder! "
            "I was created by Nathan on October 31st 2019. "
            f"You can hang out with me in [my server](<{self.bot.support_server_invite}>). "
            f"Type `{ctx.prefix}help` to get started."
        )
        await ctx.send(message)

    @commands.command(description="Check my latency")
    async def ping(self, ctx):
        await ctx.send(f"My latency is {int(self.bot.latency*1000)}ms")

    @commands.command(description="Get the uptime", aliases=["up"], invoke_without_command=True)
    async def uptime(self, ctx):
        await ctx.send(f"I started up {human_time.timedelta(self.bot.uptime, accuracy=None)}")

    @commands.command(description="Get a link to join the support server")
    async def support(self, ctx):
        await ctx.send(self.bot.support_server_invite)

    @commands.command(description="Get a link to add me to your server")
    async def invite(self, ctx):
        perms  = discord.Permissions.none()
        perms.kick_members = True
        perms.ban_members = True
        perms.manage_channels = True
        perms.manage_guild = True
        perms.add_reactions = True
        perms.view_audit_log = True
        perms.read_messages = True
        perms.send_messages = True
        perms.manage_messages = True
        perms.embed_links = True
        perms.attach_files = True
        perms.read_message_history = True
        perms.external_emojis = True
        perms.connect = True
        perms.speak = True
        perms.manage_roles = True
        perms.request_to_speak = True

        invite = discord.utils.oauth_url(self.bot.user.id, permissions=perms)
        await ctx.send(f"<{invite}>")

    @commands.command(description="Gives an overview of the codebase")
    async def code(self, ctx):
        file_count = 0
        line_count = 0
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

                            if line.startswith("class "):
                                class_count += 1
                            if line.startswith("def "):
                                function_count += 1

        em = discord.Embed(
            title="Codebase Overview",
            description=f"I'm crafted with discord.py v{discord.__version__} and Python v{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}",
            color=0x96c8da
        )
        em.add_field(name="Files", value=file_count, inline=False)
        em.add_field(name="Lines", value=line_count, inline=False)
        em.add_field(name="Classes", value=class_count, inline=False)
        em.add_field(name="Functions", value=function_count, inline=False)
        await ctx.send(embed=em)

    @commands.group(description="Manages custom prefixes for the server", invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send_help(ctx.command)

    @prefix.command(name="add", description="Adds a prefix to the server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_add(self, ctx, *, prefix: PrefixConverter):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)
        if prefix in prefixes:
            return await ctx.send("That prefix is already added.")

        if len(prefixes) > 10:
            return await ctx.send("You cannot have more than 10 custom prefixes.")

        prefixes.append(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Added the prefix `{prefix}`.")

    @prefix.command(name="remove", description="Remove a prefix from the server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_remove(self, ctx, *, prefix: PrefixConverter):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)

        if prefix not in prefixes:
            return await ctx.send("That prefix is not added")

        prefixes.remove(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Removed the prefix `{prefix}`.")

    @prefix.command(name="default", description="Set a prefix as the first prefix for the server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_default(self, ctx, *, prefix: PrefixConverter):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)

        if prefix in prefixes:
            prefixes.remove(prefix)

        if len(prefixes) >= 10:
            return await ctx.send("You cannot have more than 10 prefixes.")

        prefixes = [prefix] + prefixes
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Set `{prefix}` as the default prefix.")

    @prefix.command(name="clear", description="Removes all the prefixes from the server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_clear(self, ctx):
        result = await menus.Confirm("Are you sure you want to clear all your prefixes?").prompt(ctx)

        if result is False:
            return await ctx.send("Aborting")

        await self.bot.prefixes.add(ctx.guild.id, [])
        await ctx.send(f"Removed all prefixes.")

    @prefix.command(name="reset", description="Resets the server prefixes")
    @commands.has_permissions(manage_guild=True)
    async def prefix_reset(self, ctx):
        result = await menus.Confirm("Are you sure you want to reset your prefixes to the default prefixes?").prompt(ctx)

        if result is False:
            return await ctx.send("Aborting")

        await self.bot.prefixes.remove(ctx.guild.id)
        await ctx.send(f"Reset prefixes to default prefixes.")

    @prefix.command(name="list", description="Shows the server prefies")
    async def prefix_list(self, ctx):
        prefixes = await self.bot.get_prefix(ctx.message)
        prefixes.pop(0)

        em = discord.Embed(title="Prefixes", description="\n".join(f"- {prefix}" for prefix in prefixes), color=0x96c8da)
        em.set_footer(text=f"{formats.plural(len(prefixes), end='es'):prefix}")
        await ctx.send(embed=em)


async def setup(bot):
    await bot.add_cog(Meta(bot))
