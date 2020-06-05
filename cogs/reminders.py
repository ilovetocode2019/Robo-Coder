from discord.ext import commands, tasks
import discord
import asyncio
import aiosqlite
import pathlib
from datetime import datetime, date, time, timedelta, timezone
import datetime as dt
import re

def readable(seconds): 
    seconds = seconds % (24 * 3600) 
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
      
    return "%d hours, %02d minutes, and %02d seconds" % (hour, minutes, seconds)

class Reminders(commands.Cog):
    """Reminders from the bot."""
    def __init__(self, bot):
        self.bot = bot
        self.timer.start()

    def cog_unload(self):
        self.timer.cancel()

    @commands.command(name="remindlist", description="Get a list of your reminders")
    async def remindlist(self, ctx):
        cursor = await self.bot.db.execute(f"SELECT Time, Content FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}'")
        rows = await cursor.fetchall()
        em = discord.Embed(title="Reminders", color=0X00ff00)
        for row in rows:
            time = datetime.fromtimestamp(row[0])-datetime.now()
            em.add_field(name=f"in {time.days} days, {readable(time.seconds)}", value=row[1], inline=False)
        await ctx.send(embed=em)
        await cursor.close()

    @commands.command(name="remind", description="Create a reminder \nExample: r!remind 1day, Do something", usage="[time], [reminer]")
    async def add(self, ctx, *, reminder_data):
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
            await self.bot.db.execute(f"INSERT INTO Reminders('Userid', 'Guildid', 'Channid', 'Msgid', 'Time', 'Content') VALUES ('{str(ctx.author.id)}', '@me', '{ctx.author.dm_channel.id}', '{ctx.message.id}', '{int(timestamp)}', '{content}');")            
        else:
            await self.bot.db.execute(f"INSERT INTO Reminders('Userid', 'Guildid', 'Channid', 'Msgid', 'Time', 'Content') VALUES ('{str(ctx.author.id)}', '{ctx.guild.id}', '{ctx.channel.id}', '{ctx.message.id}', '{int(timestamp)}', '{content}');")
        await self.bot.db.commit()
        remindtime = sometime-datetime.utcnow()
        await ctx.send(f"✅ I will remind you in {remindtime.days} days, {readable(remindtime.seconds)}")

    @commands.command(name="unremind", description="Remove a reminder", usage="[reminder]")
    async def remindremove(self, ctx, *, content):
        cursor = await self.bot.db.execute(f"SELECT * FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}' and Reminders.Content='{content}';")
        if len(await cursor.fetchall()) == 0:
            return await ctx.send("That reminder doesn't exist")
        await cursor.close()
        await self.bot.db.execute(f"DELETE FROM Reminders WHERE Reminders.Userid='{str(ctx.author.id)}' and Reminders.Content='{content}';")
        await self.bot.db.commit()
        await ctx.send("Reminder deleted")


    async def timesend(self, seconds, channel, text):
        await asyncio.sleep(seconds)
        await channel.send(text)

    @tasks.loop(seconds=5.0)
    async def timer(self):
        cursor = await self.bot.db.execute('SELECT * FROM Reminders')
        rows = await cursor.fetchall()
        await cursor.close()
        tolaunch = []
        for row in rows:
            if int(row[4])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) < 5:
                channel = self.bot.get_channel(int(row[2]))
                user = self.bot.get_user(row[0])
                tolaunch.append(self.timesend(int(row[4])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()), channel, row[5]+"\n<@"+str(row[0])+">"))
                await self.bot.db.execute(f"DELETE FROM Reminders WHERE Reminders.Userid='{row[0]}' and Reminders.Content='{row[5]}';")
                await self.bot.db.commit()
        asyncio.gather(*tolaunch)

    @timer.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

def setup(bot):
    bot.add_cog(Reminders(bot))