import discord
from discord.ext import commands
from discord.ext import tasks

import datetime
import humanize
import asyncio
import dateparser

class TimeConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            if not arg.startswith("in") and not arg.startswith("at"):
                arg = f"in {arg}"
            time = dateparser.parse(arg, settings={"TIMEZONE": "UTC"})
        except:
            raise commands.BadArgument("Failed to parse time")
        if not time:
            raise commands.BadArgument("Failed to parse time")
        return time

class Timers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":timer:"
        self.loop.start()

    def cog_unload(self):
        self.loop.cancel()

    async def create_timer(self, event, time, extra):
        query = """INSERT INTO timers (event, time, extra)
                   VALUES ($1, $2, $3);
                """
        await self.bot.db.execute(query, event, time, extra)

    async def cancel_timer(self, timer):
        query = """DELETE FROM timers
                   WHERE timers.id=$1;
                """
        await self.bot.db.execute(query, timer)

    @commands.group(name="remind", description="Set a reminder", aliases=["timer"], invoke_without_command=True)
    async def remind(self, ctx, time: TimeConverter, *, content):
        await self.create_timer("timer", time, [ctx.author.id, ctx.channel.id, ctx.message.jump_url, content])
        await ctx.send(f":white_check_mark: Set timer for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @remind.command(name="list", description="View your reminders")
    async def remind_list(self, ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'timer'
                   AND extra #>> '{0}' = $1;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id))

        if len(timers) == 0:
            return await ctx.send(":x: No running timers")

        em = discord.Embed(title="Timers", description="\n", color=0x96c8da)
        for timer in timers:
            em.description += f"\n{timer['extra'][3]} `({timer['id']})` in {humanize.naturaldelta(timer['time']-datetime.datetime.utcnow())}"
        await ctx.send(embed=em)

    @remind.command(name="here", description="View your reminders here")
    async def remind_here(self ,ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'timer'
                   AND extra #>> '{0}' = $1
                   AND extra #>> '{1}' = $2;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id), str(ctx.channel.id))

        if len(timers) == 0:
            return await ctx.send(":x: No running timers here")

        em = discord.Embed(title="Timers Here", description="\n", color=0x96c8da)
        for timer in timers:
            em.description += f"\n{timer['extra'][3]} `({timer['id']})` in {humanize.naturaldelta(timer['time']-datetime.datetime.utcnow())}"
        await ctx.send(embed=em)

    @remind.command(name="cancel", description="Cancel a reminder", aliases=["remove", "delete"])
    async def remind_cancel(self, ctx, timer: int):
        query = """DELETE FROM timers
                   WHERE id=$1
                   AND event = 'timer'
                   AND extra #>> '{0}' = $2;
                """
        result = await self.bot.db.execute(query, timer, str(ctx.author.id))
        if result == "DELETE 0":
            return await ctx.send(":x: That is not a valid timer or you do not own it")

        await ctx.send(":white_check_mark: Timer has been canceled")

    @commands.Cog.listener()
    async def on_timer_complete(self, timer):
        time = (timer["time"]-datetime.datetime.utcnow())
        if time.days == 0:
            await asyncio.sleep(time.seconds)

        channel = self.bot.get_channel(timer["extra"][1])
        user = self.bot.get_user(timer["extra"][0])
        content = timer["extra"][3]
        created_at = timer["created_at"]

        em = discord.Embed(title=content, color=0x96c8da)
        em.add_field(name="When", value=f"{humanize.naturaldelta(datetime.datetime.utcnow()-created_at)} ago")
        await channel.send(content=user.mention, embed=em)

    @tasks.loop(seconds=30)
    async def loop(self):
        query = """SELECT * FROM timers;"""
        timers = await self.bot.db.fetch(query)
        for timer in timers:
            time = timer["time"]-datetime.datetime.utcnow()
            if (time.seconds < 30 and time.days == 0) or (time.days < 0):
                self.bot.dispatch(f"{timer['event']}_complete", timer)
                query = """DELETE FROM timers
                           WHERE timers.id=$1;
                        """
                await self.bot.db.execute(query, timer["id"])

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Timers(bot))