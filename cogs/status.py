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
        await self.bot.status_webhook.send("I have connected to discord.")

        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "online", int(timestamp))

    @commands.Cog.listener("on_resumed")
    async def on_resumed(self):
        await self.bot.status_webhook.send("I have resumed connection with discord.")

        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "online", int(timestamp))

    @commands.Cog.listener("on_disconnect")
    async def on_disconnect(self):
        await self.bot.status_webhook.send("I have disconnected from discord.")

        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "offline", int(timestamp))
        
def setup(bot):
    bot.add_cog(Status(bot))