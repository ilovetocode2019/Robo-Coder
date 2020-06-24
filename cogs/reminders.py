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

        timestamp = remindtime.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(ctx.channel, discord.channel.DMChannel):
            query = (f'''INSERT INTO reminders(userid, guildid, channid, msgid, time, content) VALUES ($1, $2, $3, $4, $5, $6)''', str(ctx.author.id), "@me", str(ctx.author.dm_channel.id), str(ctx.message.id), int(timestamp), content)
            await self.bot.db.execute(*query)
        else:
            query = (f'''INSERT INTO reminders(userid, guildid, channid, msgid, time, content) VALUES ($1, $2, $3, $4, $5, $6)''', str(ctx.author.id), str(ctx.guild.id), str(ctx.channel.id), str(ctx.message.id), int(timestamp), content)
            await self.bot.db.execute(*query)
        if remindtime.tzinfo:
            now = datetime.utcnow().replace(tzinfo=remindtime.tzinfo)
        else:
            now = datetime.utcnow()

        time_till = remindtime-now

        await ctx.send(f"✅ '{content}' in {time_till.days} days, {time_utils.readable(time_till.seconds)}")

    @remind.command(name="delete", description="Remove a reminder", aliases=["remove"], usage="[id]")
    async def remindremove(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM reminders WHERE reminders.userid='{str(ctx.author.id)}' and reminders.id={content};")
        if len(rows) == 0:
            return await ctx.send("That reminder doesn't exist")
        await self.bot.db.execute(f"DELETE FROM reminders WHERE reminders.userid='{str(ctx.author.id)}' and reminders.id={content};")
        await ctx.send("Reminder deleted")

    @remind.command(name="list", description="Get a list of your reminders")
    async def remindlist(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT id, time, Content FROM reminders WHERE reminders.userid='{str(ctx.author.id)}'")
        em = self.bot.build_embed(title="reminders", description="", color=custom.colors.notes)
        for row in rows:
            time = datetime.fromtimestamp(row[1])-datetime.now()
            em.add_field(name=f"in {time.days} days, {time_utils.readable(time.seconds)}", value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)


    async def dispatch_timer(self, seconds, channel, text, query):
        await asyncio.sleep(seconds)
        await channel.send(text)
        await self.bot.db.execute(query)

    @tasks.loop(seconds=5.0)
    async def timer(self):
        rows = await self.bot.db.fetch('SELECT id, userid, guildid, channid, msgid, time, content FROM reminders')
        for row in rows:
            if int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) < 5:
                channel = self.bot.get_channel(int(row[3]))
                user = self.bot.get_user(row[1])
                time = int(row[5])-int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
                query = f"DELETE FROM reminders WHERE reminders.userid='{row[1]}' and reminders.id='{row[0]}';"
                link = f"https://discord.com/channels/{row[2]}/{row[3]}/{row[4]}"
                mention = "<@"+str(row[1])+">"
                self.bot.loop.create_task(self.dispatch_timer(time, channel, f"{mention}: {row[6]}\n{link}", query))

    @timer.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)

def setup(bot):
    bot.add_cog(Reminders(bot))