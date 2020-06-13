from discord.ext import commands
from discord.ext import tasks
import discord

from datetime import datetime

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queries = []
        self.log_commands.start()

    def cog_unload(self):
        self.log_commands.cancel()

    @commands.Cog.listener("on_command_completion")
    @commands.guild_only()
    async def on_command(self, ctx):
        self.queries.append(("INSERT INTO Commands(Userid, Guildid, Command, Time) Values($1, $2, $3, $4)", str(ctx.author.id), str(ctx.guild.id), str(ctx.command), int(datetime.timestamp(datetime.now()))))
    
    @commands.command(name="stats", description="Look at command usage for the current guild")
    @commands.guild_only()
    async def stats(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT * FROM Commands WHERE Commands.Guildid='{ctx.guild.id}';")
        await ctx.send(f"{len(rows)} commands have been used on this server")

    @tasks.loop(seconds=15)
    async def log_commands(self):
        for query in self.queries:
            await self.bot.db.execute(*query)
        self.queries = []

def setup(bot):
    bot.add_cog(Stats(bot))