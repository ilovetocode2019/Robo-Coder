from discord.ext import commands
import discord

import traceback
import psutil
import humanize

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
        em.add_field(name="CPU", value=f"{psutil.cpu_percent()}% used with {psutil.cpu_count()} CPUs", color=0x96c8da)

        mem = psutil.virtual_memory()
        em.add_field(name="Memory", value=f"{humanize.naturalsize(mem.used)}/{humanize.naturalsize(mem.total)} ({mem.percent}% used)")

        disk = psutil.disk_usage("/")
        em.add_field(name="Disk", value=f"{humanize.naturalsize(disk.used)}/{humanize.naturalsize(disk.total)} ({disk.percent}% used)")

        await ctx.send(embed=em)

    @commands.command(name="logout", description="Logout command")
    @commands.is_owner()
    async def logout(self, ctx):
        await ctx.send(":wave: Logging out")
        await self.bot.logout()

def setup(bot):
    bot.add_cog(Admin(bot))
