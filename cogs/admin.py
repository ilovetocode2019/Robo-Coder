from discord.ext import commands, menus
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
from jishaku.codeblocks import codeblock_converter

class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=30.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self.msg)

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def do_confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button('\N{CROSS MARK}')
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True
    
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

    @commands.command(name="process", description="Get info about the memory and CPU usage")
    async def process(self, ctx):
        em = discord.Embed(title="Process", color=0x96c8da)
        em.add_field(name="CPU", value=f"{psutil.cpu_percent()}% used with {psutil.cpu_count()} CPUs")

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

        if execute:
            return await ctx.send(f"Executed in {int((end-start)*1000)}ms: {str(results)}")

        results = "\n".join([str(record) for record in results])

        if not results:
            return await ctx.send("No results to display")

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
        result = await Confirm(f"Are you sure you want to update the following cogs:\n{cogs_text}").prompt(ctx)
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

def setup(bot):
    bot.add_cog(Admin(bot))
