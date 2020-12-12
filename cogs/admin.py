from discord.ext import commands, menus, tasks
import discord

import traceback
import psutil
import humanize
import re
import os
import asyncio
import subprocess
import time
import traceback
import io
import pkg_resources
from jishaku.codeblocks import codeblock_converter

from .utils import menus, formats

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_loop.start()
        self.hidden = True

    def cog_unload(self):
        self.update_loop.cancel()

    def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id

    @commands.group(name="reload", description="Reload an extension", invoke_without_command=True)
    @commands.is_owner()
    async def _reload(self, ctx, cog):
        try:
            self.bot.reload_extension(cog.lower())
            await ctx.send(f"**:repeat: Reloaded** `{cog.lower()}`")
            print(f"Extension '{cog.lower()}' successfully reloaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not reloaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not reloaded.\n{traceback_data}")

    @commands.command(name="process", description="View system stats")
    async def process(self, ctx):
        em = discord.Embed(title="Process", color=0x96c8da)
        em.add_field(name="CPU", value=f"{psutil.cpu_percent()}% used with {formats.plural(psutil.cpu_count()):CPU}")

        mem = psutil.virtual_memory()
        em.add_field(name="Memory", value=f"{humanize.naturalsize(mem.used)}/{humanize.naturalsize(mem.total)} ({mem.percent}% used)")

        disk = psutil.disk_usage("/")
        em.add_field(name="Disk", value=f"{humanize.naturalsize(disk.used)}/{humanize.naturalsize(disk.total)} ({disk.percent}% used)")

        await ctx.send(embed=em)

    @commands.command(name="sql", description="Run some sql")
    async def sql(self, ctx, *, code: codeblock_converter):
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

    @commands.command(name="update", description="Update the bot")
    async def update(self, ctx):
        await ctx.trigger_typing()

        regex = re.compile(r"\s*(?P<filename>.+?)\s*\|\s*[0-9]+\s*[+-]+")

        process = await asyncio.create_subprocess_shell("git pull", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = await process.communicate()
        text = stdout.decode()

        files = regex.findall(text)
        cogs = []
        for file in files:
            root, ext = os.path.splitext(file)
            if root.startswith("cogs/") and root.count("/") == 1 and ext == ".py":
                cogs.append(root.replace("/", "."))

        if not cogs:
            return await ctx.send("No cogs to update")

        cogs_text = "\n".join(cogs)
        result = await menus.Confirm(f"Are you sure you want to update the following cogs:\n{cogs_text}").prompt(ctx)
        if not result:
            return await ctx.send(":x: Aborting")

        text = ""
        for cog in cogs:
            try:
                self.bot.reload_extension(cog)
                text += f"\n:white_check_mark: {cog}"
            except:
                text += f"\n:x: {cog}"

        await ctx.send(text)

    @commands.command(name="logout", description="Logout the bot")
    @commands.is_owner()
    async def logout(self, ctx):
        await ctx.send(":wave: Logging out")
        await self.bot.logout()

    @tasks.loop(hours=10)
    async def update_loop(self):
        with open("requirements.txt") as file:
            lines = file.read()
            installed = lines.split("\n")

        outdated = []
        for package in installed:
            try:
                current_version = pkg_resources.get_distribution(package).version
                async with self.bot.session.get(f"https://pypi.org/pypi/{package}/json") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pypi_version = data["info"]["version"]
                        if current_version != pypi_version:
                            outdated.append((package, current_version, pypi_version))
            except:
                pass

        if outdated:
            em = discord.Embed(title="Outdated Packages", description="", color=0x96c8da)
            for package in outdated:
                em.description += f"\n{package[0]} (Local: {package[1]} | PyPI: {package[2]})"

            await self.bot.console.send(embed=em)

    @update_loop.before_loop
    async def before_update_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Admin(bot))
