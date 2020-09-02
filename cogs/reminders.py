from discord.ext import commands, tasks
import discord
import asyncio
import pathlib

from datetime import datetime, date, time, timedelta, timezone
import datetime as dt
import dateparser

import time as time_module

from .utils import time as time_utils
from .utils import custom
class Reminders(commands.Cog):
    """Reminders on Discord."""

    def __init__(self, bot):
        self.bot = bot
        self.timer.start()

    def cog_unload(self):
        self.timer.cancel()

    @commands.group(name="remind", description="Create a reminder \nExample: r!remind 1day, Do something", usage="[time], [reminer]", invoke_without_command=True)
    async def remind(self, ctx, *, reminder_data):
        #Parse the time
        try:
            data = reminder_data.split(", ")
            time = data[0]
            content = ", ".join(data[1:])
        except IndexError:
            time = reminder_data
            content = "No reminder content"

        if not time.startswith("in") and not time.startswith("at"):
            time = f"in {time}"

        try:
            remindtime = dateparser.parse(time, settings={'TIMEZONE': 'UTC'})
        except:
            return await ctx.send("Couldn't parse your time")

        if not remindtime:
            return await ctx.send("Couldn't parse your time")
        
        #Insert it into the db
        timestamp = remindtime.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(ctx.channel, discord.channel.DMChannel):
            query = (f'''INSERT INTO reminders(userid, guildid, channid, msgid, time, content) VALUES ($1, $2, $3, $4, $5, $6)''', ctx.author.id, "@me", ctx.author.dm_channel.id, ctx.message.id, int(timestamp), content)
            await self.bot.db.execute(*query)
        else:
            query = (f'''INSERT INTO reminders(userid, guildid, channid, msgid, time, content) VALUES ($1, $2, $3, $4, $5, $6)''', ctx.author.id, ctx.guild.id, ctx.channel.id, ctx.message.id, int(timestamp), content)
            await self.bot.db.execute(*query)

        #Replace the datetime with the tzinfo if needed
        if remindtime.tzinfo:
            now = datetime.utcnow().replace(tzinfo=remindtime.tzinfo)
        else:
            now = datetime.utcnow()

        time_till = remindtime-now
        
        #Send the finishing message
        await ctx.send(f"✅ '{content}' in {time_utils.readable(time_till)}")

    @remind.command(name="delete", description="Remove a reminder", aliases=["remove"], usage="[id]")
    async def remindremove(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM reminders WHERE reminders.userid=$1 AND reminders.id=$2", ctx.author.id, content)
        if len(rows) == 0:
            return await ctx.send("That reminder doesn't exist")
        await self.bot.db.execute("DELETE FROM reminders WHERE reminders.userid=$1 AND reminders.id=$2", ctx.author.id, content)
        await ctx.send("Reminder deleted")

    @remind.command(name="list", description="Get a list of your reminders")
    async def remindlist(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT id, time, Content FROM reminders WHERE reminders.userid=$1", ctx.author.id)
        em = self.bot.build_embed(title="Reminders", description="", color=custom.Color.notes)
        for row in rows:
            time = datetime.fromtimestamp(row[1])-datetime.now()
            em.add_field(name=f"in {time_utils.readable(time)}", value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)


    async def dispatch_timer(self, seconds, channel, text, query):
        """Waits a time, the runs reminders the timer, and exectues a delete query"""
        await asyncio.sleep(seconds)
        await channel.send(text)
        await self.bot.db.execute(*query)

    @tasks.loop(seconds=5.0)
    async def timer(self):
        """Loop that waits for a reminder to be found"""

        rows = await self.bot.db.fetch('SELECT id, userid, guildid, channid, msgid, time, content FROM reminders')
        for row in rows:
            if int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) < 5:
                channel = self.bot.get_channel(int(row[3]))
                user = self.bot.get_user(row[1])
                time = int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
                query = ("DELETE FROM reminders WHERE reminders.userid=$1 AND reminders.id=$2", row[1], int(row[0]))
                link = f"https://discord.com/channels/{row[2]}/{row[3]}/{row[4]}"
                mention = "<@"+str(row[1])+">"
                self.bot.loop.create_task(self.dispatch_timer(time, channel, f"{mention}: {row[6]}\n{link}", query))

    @timer.before_loop
    async def before_timer(self):
        """Waits till the bot is ready before checking timers"""

        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

def setup(bot):
    bot.add_cog(Reminders(bot))