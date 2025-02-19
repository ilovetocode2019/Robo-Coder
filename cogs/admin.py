import discord
from discord.ext import commands, tasks

import asyncio
import datetime
import humanize
import importlib
import io
import os
import re
import psutil
import subprocess
import sys
import time
import traceback
from jishaku import codeblocks
from typing import Union

from .utils import formats, human_time, menus


class Admin(commands.Cog):
    """Private administrative commands."""

    emoji = "\N{PERSONAL COMPUTER}"

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(description="Reloads an extension")
    async def reload(self, ctx, *extensions):
        if len(extensions) == 0:
            extensions = self.bot.extensions.values()

        if len(extensions) > 1:
            message = []
            for extension in extensions:
                try:
                    await self.bot.reload_extension(extension)
                    message.append(f":repeat: Reloaded `{extension}`")
                except commands.ExtensionError as exc:
                    message.append(f":warning: Failed to reload `{extension}`")
            await ctx.send("\n\n".join(message))
        else:
            try:
                await self.bot.reload_extension(extensions[0])
                await ctx.send(f":repeat: Reloaded `{extensions[0]}`")
            except commands.ExtensionError as exc:
                full = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, 1))
                await ctx.send(f":warning: Couldn't reload `{extensions[0]}`\n```py\n{full}```")

    @commands.command(description="Loads an extension")
    async def load(self, ctx, extension):
        try:
            await self.bot.load_extension(extension)
            await ctx.send(f":inbox_tray: Loaded `{extension}`")
        except commands.ExtensionError as exc:
            full = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, 1))
            await ctx.send(f":warning: Couldn't load `{extension}`\n```py\n{full}```")

    @commands.command(description="Unloads an extension")
    async def unload(self, ctx, extension):
        try:
            await self.bot.unload_extension(extension)
            await ctx.send(f":outbox_tray: Unloaded `{extension}`")
        except commands.ExtensionError as exc:
            full = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, 1))
            await ctx.send(f":warning: Couldn't unload `{extension}`\n```py\n{full}```")

    @commands.command(description="Pulls the latest changes and reloads affected extensions")
    async def update(self, ctx):
        async with ctx.typing():
            # Run git pull to update bot
            process = await asyncio.create_subprocess_shell("git pull", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await process.communicate()
            text = stdout.decode()

            # Find modules that need reloading
            modules = []
            regex = re.compile(r"\s*(?P<filename>.+?)\s*\|\s*[0-9]+\s*[+-]+")
            files = regex.findall(text)

            for file in files:
                root, module = os.path.splitext(file)
                if module != ".py":
                    continue
                if root.startswith("cogs/") and root.count("/") == 1:
                    modules.append((root.count("/")-1, root.replace("/", ".")))

            modules.sort(reverse=True)

        if not modules:
            return await ctx.send("Already up-to-date")

        joined = "\n".join([module for is_module, module in modules])
        result = await menus.Confirm(f"Are you sure you want to update the followings modules?\n{joined}").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        # Reload all the modules
        results = []
        for is_module, module in modules:
            if is_module:
                try:
                    lib = sys.modules[module]
                    try:
                        importlib.reload(lib)
                        results.append((True, module))
                    except:
                        results.append((False, module))
                except KeyError:
                    results.append((None, module))

            else:
                try:
                    try:
                        await self.bot.reload_extension(module)
                    except commands.ExtensionNotLoaded:
                        self.bot.load_extension(module)
                    results.append((True, module))
                except:
                    results.append((False, module))

        message = ""
        for status, module in results:
            if status == True:
                message += f"\n:white_check_mark: {module}"
            elif status == False:
                message += f"\n:x: {module}"
            else:
                message += f"\n:zzz: {module}"

        await ctx.send(message)

    @commands.command(description="Executes a sql query on the database")
    async def sql(self, ctx, *, code: codeblocks.codeblock_converter):
        _, query = code

        execute = query.count(";") > 1

        if execute:
            method = self.bot.db.execute
        else:
            method = self.bot.db.fetch

        try:
            start = time.time()
            results = await method(query)
            end = time.time()
        except Exception as e:
            full = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            return await ctx.send(f"```py\n{full}```")

        if not results:
            return await ctx.send("No results to display")

        if execute:
            return await ctx.send(f"Executed in {int((end-start)*1000)}ms: {str(results)}")

        columns = list(results[0].keys())
        rows = [list(row.values()) for row in results]

        table = formats.Tabulate()
        table.add_columns(columns)
        table.add_rows(rows)
        results = str(table)

        try:
            await ctx.send(f"Executed in {int((end-start)*1000)}ms\n```{results}```")
        except discord.HTTPException:
            await ctx.send(file=discord.File(io.BytesIO(str(results).encode("utf-8")), filename="result.txt"))

    @commands.command(description="Displays operating system stats", aliases=["system", "health"])
    async def process(self, ctx):
        em = discord.Embed(title="Process", color=0x96c8da)
        em.add_field(name="CPU", value=f"{psutil.cpu_percent()}% used with {formats.plural(psutil.cpu_count()):CPU}")
        mem = psutil.virtual_memory()
        em.add_field(name="Memory", value=f"{humanize.naturalsize(mem.used)}/{humanize.naturalsize(mem.total)} ({mem.percent}% used)")
        disk = psutil.disk_usage("/")
        em.add_field(name="Disk", value=f"{humanize.naturalsize(disk.used)}/{humanize.naturalsize(disk.total)} ({disk.percent}% used)")
        await ctx.send(embed=em)

    @commands.command(description="Logs out the bot")
    @commands.is_owner()
    async def logout(self, ctx):
        await ctx.send(":wave: Logging out")
        await self.bot.close()

    @commands.command(description="Adds a user or server to the blacklist", aliases=["block"], invoke_without_subcommand=True)
    async def blacklist(self, ctx, entity: Union[discord.User, discord.Guild, discord.Object], *, until: human_time.FutureTime = None):
        if await self.bot.get_blacklisted(entity) is not None:
            return await ctx.send("\N{CROSS MARK} Entity is already blacklisted")

        if isinstance(entity, discord.Guild):
            await entity.leave()

        if until is not None:
            await self.bot.blacklist.add(entity.id, until.time.timestamp())
            await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Entity added to blacklist until {discord.utils.format_dt(until.time)}")
        else:
            await self.bot.blacklist.add(entity.id, True)
            await ctx.send("\N{WHITE HEAVY CHECK MARK} Entity permanently added to blacklist")

    @commands.command(description="Shows the blacklist of a user", aliases=["blocked"])
    async def blacklisted(self, ctx, *, entity: Union[discord.User, discord.Guild, discord.Object]):
        blacklisted = await self.bot.get_blacklisted(entity)

        if blacklisted is None:
            await ctx.send("Entity is not blacklisted")
        elif blacklisted is True:
            await ctx.send("Entity is permanently blacklisted")
        else:
            until = datetime.datetime.fromtimestamp(blacklisted, tz=datetime.UTC)
            await ctx.send(f"Entity is blacklisted until {discord.utils.format_dt(until)}")

    @commands.command(description="Removes a user or server from the blacklist", aiases=["unblock"])
    async def unblacklist(self, ctx, *, entity: Union[discord.User, discord.Guild, discord.Object]):
        if await self.bot.get_blacklisted(entity) is None:
            return await ctx.send("\N{CROSS MARK} Entity is not blacklisted")

        await self.bot.blacklist.remove(entity.id)
        await ctx.send("\N{WHITE HEAVY CHECK MARK} Entity removed from blacklist")

async def setup(bot):
    await bot.add_cog(Admin(bot))
