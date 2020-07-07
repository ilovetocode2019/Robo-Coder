from discord.ext import commands
from discord.ext import tasks
import discord

import datetime
import os

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_connect")
    async def on_connect(self):
        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "online", int(timestamp))

    @commands.Cog.listener("on_disconnect")
    async def on_disconnect(self):
        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "offline", int(timestamp))

    @commands.command(name="status", description="Get the overall uptime or me")
    async def status(self, ctx):
        rows = await self.bot.db.fetch("SELECT * FROM status_updates WHERE status_updates.userid=$1", str(self.bot.user.id))
        status = {}
        for x, row in enumerate(rows):
            if len(rows) == x+1:
                time = datetime.datetime.timestamp(datetime.datetime.now())-row[2]
            else:
                time = rows[x+1][2]-row[2]
            
            if row[1] in status:
                status[row[1]] += time
            else:
                status[row[1]] = time
        
        total = sum(status.values())
        await ctx.send(f"I am online {(status['online']/total)*100}% of the time")
def setup(bot):
    bot.add_cog(Status(bot))