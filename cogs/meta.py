import os
import sys
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from .utils import errors, formats, human_time, menus

class Prefix(commands.Converter):
    async def convert(self, ctx, prefix):
        if discord.utils.escape_mentions(prefix) != prefix:
            raise commands.BadArgument("Prefix can't include a mention")
        return prefix

class RoboCoderHelpCommand(commands.HelpCommand):
    bottom_text = "\n\nKey: `<required> [optional]`. **Remove <> and [] when using the command**."

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(
            title=f"{bot.user.name} Help",
            description=f"{bot.description}. Use `{ctx.clean_prefix}help [command]` or `{ctx.clean_prefix}help [Category]` for more specific help. If you have any questions or issues, feel free to [join the support server]({bot.support_server_invite}).",
            color=0x96c8da
        )

        message = ""
        for name, cog in sorted(bot.cogs.items()):
            if not getattr(cog, "hidden", False):
                message += f"\n{getattr(cog, 'emoji', '')} {cog.qualified_name}"
        em.add_field(name="Categories", value=message)
        em.set_footer(text=bot.user.name, icon_url=bot.user.display_avatar.url)
        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{getattr(cog, 'emoji', '')} {cog.qualified_name}", description="\n", color=0x96c8da)
        commands = await self.filter_commands(cog.walk_commands())
        for command in commands:
            em.description += f"\n`{self.get_command_signature(command).strip()}` {'-' if command.description else ''} {command.description}"

        em.description += self.bottom_text
        em.set_footer(text=bot.user.name, icon_url=bot.user.display_avatar.url)

        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{command.name} {command.signature.strip()}", description=command.description or "", color=0x96c8da)
        if command.aliases:
            em.description += f"\nAliases: {', '.join(command.aliases)}"
        em.description += self.bottom_text
        em.set_footer(text=bot.user.name, icon_url=bot.user.display_avatar.url)

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

        em.description += self.bottom_text
        em.set_footer(text=bot.user.name, icon_url=bot.user.display_avatar.url)

        await ctx.send(embed=em)

class Meta(commands.Cog):
    """Stuff related to the bot itself."""

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
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        if isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("This command can only be used in DMs.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in DMs.")
        elif isinstance(error, commands.BotMissingPermissions):
            perms_text = "\n".join([f"- {perm.replace('_', ' ').capitalize()}" for perm in error.missing_perms])
            await ctx.send(f"I am missing some permissions:\n {perms_text}") 
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
            await ctx.send(f"{error}")
        elif isinstance(error, errors.VoiceError) and str(error):
            await ctx.send(f"{error}")

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
            em.description += f"\n\n```py\n{error}```\n"

            if self.bot.console:
                await self.bot.console.send(embed=em)

    async def on_interaction_error(self, interaction, error):
        if not interaction.command:
            return

        print(f"Ignoring exception in slash command {interaction.command.name}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        if isinstance(error, app_commands.CommandInvokeError):
            em = discord.Embed(
                title=":warning: Error",
                description=f"An unexpected error has occured. If you're confused or need help, feel free to [join the support server]({self.bot.support_server_invite}). \n```py\n{error}```",
                color=discord.Color.gold()
            )
            em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

            try:
                await interaction.response.send_message(embed=em, ephemeral=True)
            except:
                await interaction.followup.send(embed=em, ephemeral=True)

            em = discord.Embed(title=":warning: Slash Command Error", description="", color=discord.Color.gold())
            em.description += f"\nCommand: `{interaction.command.name}`"
            em.description += f"\nLink: [Jump]({interaction.channel.jump_url})"
            em.description += f"\n\n```py\n{error}```\n"

            if self.bot.console:
                await self.bot.console.send(embed=em)

    @app_commands.command(name="help", description="Get help on the bot")
    async def help(self, interaction):
        em = discord.Embed(
            title=f"{self.bot.user.name} Help",
            description=f"{self.bot.description}. If you have any questions or issues, feel free to [join the support server]({self.bot.support_server_invite}). \n\nIn order to use slash commands, type / and then the command name to use a command, or type / and then select the {self.bot.user.mention} section to view a list of commands. \n\nDiscord may remove prefixed commands in the future, so slash commands are the recommended way to use commands.",
            color=0x96c8da
        )
        em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=em)

    @commands.hybrid_command(name="hi", description="Say hello", aliases=["hello"])
    async def hi(self, ctx):
        await ctx.send(f":wave: Hello, I am Robo Coder!\nTo get more info type: {ctx.prefix}help")

    @commands.hybrid_command(name="ping", description="Check my latency")
    async def ping(self, ctx):
        await ctx.send(f"My latency is {int(self.bot.latency*1000)}ms")

    @commands.hybrid_command(name="uptime", description="Get the uptime", aliases=["up"], invoke_without_command=True)
    async def uptime(self, ctx):
        await ctx.send(f"I started up {human_time.timedelta(self.bot.uptime, accuracy=None)}")

    @commands.hybrid_command(name="support", description="Get a link to join the support server")
    async def support(self, ctx):
        await ctx.send(self.bot.support_server_invite)

    @commands.hybrid_command(name="invite", description="Get a link to add me to your server")
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

    @commands.hybrid_command(name="code", description="Find out what I'm made of")
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

    @commands.group(name="prefix", description="Manage custom prefixes for this server", invoke_without_command=True)
    async def prefix(self, ctx):
        await ctx.send_help(ctx.command)

    @prefix.command(name="add", description="Add a prefix to this server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_add(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)
        if prefix in prefixes:
            return await ctx.send("That prefix is already added.")

        if len(prefixes) > 10:
            return await ctx.send("You cannot have more than 10 custom prefixes.")

        prefixes.append(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Added the prefix `{prefix}`.")

    @prefix.command(name="remove", description="Remove a prefix from this server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_remove(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)
        if prefix not in prefixes:
            return await ctx.send("That prefix is not added.")

        prefixes.remove(prefix)
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Removed the prefix `{prefix}`.")

    @prefix.command(name="default", description="Set a prefix as the first prefix")
    @commands.has_permissions(manage_guild=True)
    async def prefix_default(self, ctx, *, prefix: Prefix):
        prefixes = self.bot.get_guild_prefixes(ctx.guild.id)
        if prefix in prefixes:
            prefixes.remove(prefix)

        if len(prefixes) >= 10:
            return await ctx.send("You cannot have more than 10 prefixes.")

        prefixes = [prefix] + prefixes
        await self.bot.prefixes.add(ctx.guild.id, prefixes)

        await ctx.send(f"Set `{prefix}` as the default prefix.")

    @prefix.command(name="clear", description="Clear all the prefixes in this server")
    @commands.has_permissions(manage_guild=True)
    async def prefix_clear(self, ctx):
        result = await menus.Confirm("Are you sure you want to clear all your prefixes?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await self.bot.prefixes.add(ctx.guild.id, [])
        await ctx.send(f"Removed all prefixes.")

    @prefix.command(name="reset", description="Reset the custom server prefixes to the default prefixes")
    @commands.has_permissions(manage_guild=True)
    async def prefix_reset(self, ctx):
        result = await menus.Confirm("Are you sure you want to reset your prefixes to the default prefixes?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await self.bot.prefixes.remove(ctx.guild.id)
        await ctx.send(f"Reset prefixes to default prefixes.")

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
        if message.content in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>") and not message.author.bot:
            prefix = self.bot.get_guild_prefix(message.guild.id)
            await message.reply(f":wave: Hello, I'm Robo Coder!\nTo get more info type: {prefix}help")

async def setup(bot):
    await bot.add_cog(Meta(bot))
