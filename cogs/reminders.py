from discord.ext import commands, tasks
import discord
import asyncio
import pathlib
from datetime import datetime, date, time, timedelta, timezone
import datetime as dt
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
        rows = await self.bot.db.fetch(f"SELECT ID FROM Reminders;")
        if len(rows) == 0:
            rows = [[0]]
        try:
            time, content = reminder_data.split(", ")
        except ValueError:
            return await ctx.send("Invalid reminder format. Try something like: `1d, Do dishes`")
        if len(re.findall("\s*-?[0-9]{1,10}\s*d", time)) > 0:
            days = re.findall("\s*-?[0-9]{1,10}\s*d", time)[0][:-1]
        else:
            days = 0
        if len(re.findall("\s*-?[0-9]{1,10}\s*h", time)) > 0:
            hours = re.findall("\s*-?[0-9]{1,10}\s*h", time)[0][:-1]
        else:
            hours = 0
        if len(re.findall("\s*-?[0-9]{1,10}\s*m", time)) > 0:
            minutes = re.findall("\s*-?[0-9]{1,10}\s*m", time)[0][:-1]
        else:
            minutes = 0
        if len(re.findall("\s*-?[0-9]{1,10}\s*s", time)) > 0:
            seconds = re.findall("\s*-?[0-9]{1,10}\s*s", time)[0][:-1]
        else:
            seconds = 0
        sometime = datetime.utcnow() + timedelta(days=int(days), hours=int(hours), minutes=int(minutes), seconds=int(seconds))
        timestamp = sometime.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(ctx.channel, discord.channel.DMChannel):
            await self.bot.db.execute(f'''INSERT INTO Reminders(ID, Userid, Guildid, Channid, Msgid, Time, Content) VALUES ($1, $2, $3, $4, $5, $6, $7)''', rows[-1][0]+1, str(ctx.author.id), "@me", str(ctx.author.dm_channel.id), str(ctx.message.id), int(timestamp), content)
        else:
            await self.bot.db.execute(f'''INSERT INTO Reminders(ID, Userid, Guildid, Channid, Msgid, Time, Content) VALUES ($1, $2, $3, $4, $5, $6, $7)''', rows[-1][0]+1, str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.id), int(timestamp), content)
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
        em = discord.Embed(title="Reminders", description="", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        for row in rows:
            time = datetime.fromtimestamp(row[1])-datetime.now()
            em.add_field(name=f"in {time.days} days, {utils_time.readable(time.seconds)}", value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)


    async def timesend(self, seconds, channel, text):
        await asyncio.sleep(seconds)
        await channel.send(text)

    @tasks.loop(seconds=5.0)
    async def timer(self):
        rows = await self.bot.db.fetch('SELECT * FROM Reminders')
        tolaunch = []
        for row in rows:
            if int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) < 5:
                channel = self.bot.get_channel(int(row[3]))
                user = self.bot.get_user(row[1])
                tolaunch.append(self.timesend(int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()), channel, row[6]+"\n<@"+str(row[1])+">"))
                await self.bot.db.execute(f"DELETE FROM Reminders WHERE Reminders.Userid='{row[1]}' and Reminders.ID='{row[0]}';")
        asyncio.gather(*tolaunch)

    @timer.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

def setup(bot):
    bot.add_cog(Reminders(bot))