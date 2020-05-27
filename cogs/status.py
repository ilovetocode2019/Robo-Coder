from discord.ext import commands, tasks
import discord
import datetime
from datetime import timedelta
import random
import asyncio

class Status(commands.Cog):
    """The cog for the status."""
    def __init__(self, bot):
        self.bot = bot
        self.status.start()
        self.activity.start()
        self.last_message = None
        self.status = "online"
        self.game_list=["Minecraft", "Rocket League", "Visual Studio Code", "Celeste", "INSIDE", "Portal", "Portal 2", None]
        self.current_game = None

    def cog_unload(self):
        self.status.cancel()
        self.activity.cancel()

    @commands.Cog.listener("on_message")
    async def record_message(self, message):
        if message.author.id == self.bot.user.id:
            self.last_message = message
            if self.status == "idle":
                self.status = "online"
                await self.bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name=self.current_game))

    @tasks.loop(seconds=5)
    async def status(self):
        if self.last_message != None:
            current_utc = datetime.datetime.utcnow()
            datetimeFormat = '%Y-%m-%d %H:%M:%S.%f'
            diff = datetime.datetime.strptime(str(current_utc), datetimeFormat)\
                 - datetime.datetime.strptime(str(self.last_message.created_at), datetimeFormat)
            minutes = float(diff.seconds)/60
            if int(minutes) == 1 and self.status=="online":
                sleep_time = random.randint(1*60, 10*60)
                await asyncio.sleep(sleep_time)
                await self.bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.playing, name=self.current_game))
                self.status = "idle"
        if self.last_message == None:
            if self.status == "online":
                sleep_time = random.randint(1*60, 10*60)
                await asyncio.sleep(sleep_time)
                self.status = "idle"
                await self.bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.playing, name=self.current_game))

    @tasks.loop(minutes=30)
    async def activity(self):
        if self.status == "online":
            await self.bot.change_presence(status=discord.Status.online, activity=None)
        if self.status == "idle":
            await self.bot.change_presence(status=discord.Status.idle, activity=None)

        self.current_game = random.choice(self.game_list)

        if self.status == "online" and self.current_game != None:
            await asyncio.sleep(60)
            await self.bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name=self.current_game))
        if self.status == "idle" and self.current_game != None:
            await asyncio.sleep(60)
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.playing, name=self.current_game))
        
                
        



def setup(bot):
    bot.add_cog(Status(bot))