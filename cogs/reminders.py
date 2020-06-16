from discord.ext import commands, tasks
import discord
import asyncio
import pathlib

from datetime import datetime, date, time, timedelta, timezone
import datetime as dt
import dateparser

from .utils import time as utils_time
import re

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer.start()

    def cog_unload(self):
        self.timer.cancel()

    @commands.group(name="remind", description="Create a reminder \nExample: r!remind 1day, Do something", usage="[time], [reminer]", invoke_without_command=True)
    async def remind(self, ctx, *, reminder_data):
        try:
            time, content = reminder_data.split(", ")
        except ValueError:
            return await ctx.send("Invalid reminder format.")

        if not time.startswith("in"):
            time = f"in {time}" 
        try:
            time_till = dateparser.parse(time)-datetime.now()
        except:
            return await ctx.send("Couldn't parse your time")
        
        sometime = datetime.utcnow() + timedelta(days=time_till.days, seconds=time_till.seconds)
        timestamp = sometime.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(ctx.channel, discord.channel.DMChannel):
            await self.bot.db.execute(f'''INSERT INTO Reminders(Userid, Guildid, Channid, Msgid, Time, Content) VALUES ($1, $2, $3, $4, $5, $6)''', str(ctx.author.id), "@me", str(ctx.author.dm_channel.id), str(ctx.message.id), int(timestamp), content)
        else:
            await self.bot.db.execute(f'''INSERT INTO Reminders(Userid, Guildid, Channid, Msgid, Time, Content) VALUES ($1, $2, $3, $4, $5, $6)''', str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.id), int(timestamp), content)
        remindtime = sometime-datetime.utcnow()
        await ctx.send(f"✅ I will remind you in {remindtime.days} days, {utils_time.readable(remindtime.seconds)}")

    @remind.command(name="delete", description="Remove a reminder", aliases=["remove"], usage="[id]")
    async def remindremove(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}' and Reminders.ID={content};")
        if len(rows) == 0:
            return await ctx.send("That reminder doesn't exist")
        await self.bot.db.execute(f"DELETE FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}' and Reminders.ID={content};")
        await ctx.send("Reminder deleted")

    @remind.command(name="list", description="Get a list of your reminders")
    async def remindlist(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT ID, Time, Content FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}'")
        if isinstance(ctx.channel, discord.DMChannel):
            em = discord.Embed(title="Reminders", description="")
        else:
            em = discord.Embed(title="Reminders", description="", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        for row in rows:
            time = datetime.fromtimestamp(row[1])-datetime.now()
            em.add_field(name=f"in {time.days} days, {utils_time.readable(time.seconds)}", value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)


    async def timesend(self, seconds, channel, text, query):
        await asyncio.sleep(seconds)
        await channel.send(text)
        await self.bot.db.execute(query)

    @tasks.loop(seconds=5.0)
    async def timer(self):
        rows = await self.bot.db.fetch('SELECT Id, Userid, Guildid, Channid, Msgid, Time, Content FROM Reminders')
        for row in rows:
            if int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) < 5:
                channel = self.bot.get_channel(int(row[3]))
                user = self.bot.get_user(row[1])
                time = int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
                query = f"DELETE FROM Reminders WHERE Reminders.Userid='{row[1]}' and Reminders.ID='{row[0]}';"
                link = f"https://discord.com/channels/{row[2]}/{row[3]}/{row[4]}"
                mention = "<@"+str(row[1])+">"
                self.bot.loop.create_task(self.timesend(time, channel, f"{mention}: {row[6]}\n{link}", query))

    @timer.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

def setup(bot):
    bot.add_cog(Reminders(bot))