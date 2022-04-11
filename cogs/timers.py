import asyncio
import datetime

import discord
from discord.ext import commands

from .utils import human_time

class Timer:
    __slots__ = ("bot", "id", "event", "data", "expires_at", "created_at")

    def __init__(self, bot, **kwargs):
        self.bot = bot
        self.id = kwargs.get("id")
        self.event = kwargs.get("event")
        self.data = kwargs.get("data")
        self.expires_at = kwargs.get("expires_at")
        self.created_at = kwargs.get("created_at")

class Timers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":timer:"

        self.loop = self.bot.loop.create_task(self.run_timers())
        self.current_timer = None
        self.timers_pending = asyncio.Event(loop=self.bot.loop)
        self.timers_pending.set()

    def cog_unload(self):
        self.loop.cancel()

    @commands.group(name="remind", description="Set a reminder", aliases=["timer", "reminder"], invoke_without_command=True)
    async def remind(self, ctx, *, reminder: human_time.TimeWithContent):
        content = reminder.content
        expires_at = reminder.time
        created_at = ctx.message.created_at

        await self.create_timer("reminder", [ctx.author.id, ctx.channel.id, ctx.message.jump_url, content], expires_at, created_at)
        await ctx.send(f"Set a reminder for `{human_time.timedelta(expires_at, when=created_at)}` with the message: `{content}`.")

    @remind.command(name="list", description="List your reminders")
    async def remind_list(self, ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id))
        timers = [Timer(self.bot, **dict(timer)) for timer in timers]
        if not timers:
            return await ctx.send("You don't have any reminders.")

        em = discord.Embed(title="Reminders", description="\n", color=0x96c8da)
        for timer in timers:
            em.description += f"\n{discord.utils.escape_markdown(timer.data[3])} `({timer.id})` in {human_time.timedelta(timer.expires_at, when=ctx.message.created_at)}"
        await ctx.send(embed=em)

    @remind.command(name="here", description="List your reminders in this channel")
    async def remind_here(self, ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1
                   AND data #>> '{1}' = $2;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id), str(ctx.channel.id))
        timers = [Timer(self.bot, **dict(timer)) for timer in timers]

        if not timers:
            return await ctx.send("You don't have any reminders in this channel.")

        em = discord.Embed(title="Reminders Here", description="\n", color=0x96c8da)
        for timer in timers:
            em.description += f"\n{discord.utils.escape_markdown(timer.data[3])} `({timer.id})` in {human_time.timedelta(timer.expires_at, when=ctx.message.created_at)}"
        await ctx.send(embed=em)

    @remind.command(name="cancel", description="Cancel a reminder", aliases=["delete", "remove"])
    async def remind_cancel(self, ctx, timer: int):
        query = """DELETE FROM timers
                   WHERE
                   timers.event=$1 AND timers.id=$2;
                """
        result = await self.bot.db.execute(query, "reminder", timer)
        if result == "DELETE 0":
            return await ctx.send("Couldn't find this reminder in your reminder list.")

        if self.current_timer and self.current_timer.event == "reminder" and self.current_timer.id == timer:
            # The timer running is the one we canceled, so we need to restart the loop
            self.restart_loop()

        await ctx.send("Reminder has been canceled.")

    @remind.command(name="clear", description="Clear all your reminders")
    async def remind_clear(self, ctx):
        query = """DELETE FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1;
                """
        result = await self.bot.db.execute(query, str(ctx.author.id))
        if result == "DELETE 0":
            return await ctx.send("No reminders to clear.")

        if self.current_timer and self.current_timer.event == "reminder" and self.current_timer.data[0] == ctx.author.id:
            self.restart_loop()

        await ctx.send("All your reminders have been cleared.")

    @commands.command(name="reminders", description="List your reminders")
    async def reminders(self, ctx):
        await ctx.invoke(self.remind_list)

    async def create_timer(self, event, data, expires_at, created_at):
        query = """INSERT INTO timers (event, data, expires_at, created_at)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id;
                """
        value = await self.bot.db.fetchval(query, event, data, expires_at, created_at)
        timer = Timer(self.bot, id=value, event=event, expires_at=expires_at, data=data, created_at=created_at)
        if self.current_timer and timer.expires_at < self.current_timer.expires_at:
            # Loop is currently sleeping for longer than the current timer so we need to cancel and re-run it
            self.restart_loop()

        self.timers_pending.set()
        return timer

    async def get_newest_timer(self):
        query = """SELECT *
                   FROM timers
                   ORDER BY timers.expires_at
                   LIMIT 1;
                """
        timer = await self.bot.db.fetchrow(query)
        if timer:
            return Timer(self.bot, **dict(timer))

    async def run_timers(self):
        await self.bot.wait_until_ready()

        while True:
            # Check for new timers
            await self.timers_pending.wait()
            timer = await self.get_newest_timer()

            if not timer:
                # We don't have any timers, so wait for timers then get the timer
                self.timers_pending.clear()
                await self.timers_pending.wait()
                timer = await self.get_newest_timer()

            # Wait until the current timer is ready to be dispatched
            self.current_timer = timer
            time = timer.expires_at-datetime.datetime.utcnow()
            if time.total_seconds():
                await asyncio.sleep(time.total_seconds())

            query = """DELETE FROM timers
                       WHERE timers.id=$1;
                    """
            await self.bot.db.execute(query, timer.id)
            self.bot.dispatch(f"{timer.event}_complete", timer)

    def restart_loop(self):
        self.loop.cancel()
        self.loop = self.bot.loop.create_task(self.run_timers())

    @commands.Cog.listener()
    async def on_reminder_complete(self, timer):
        created_at = timer.created_at
        channel = self.bot.get_channel(timer.data[1])
        user = self.bot.get_user(timer.data[0])
        content = timer.data[3]
        jump_url = timer.data[2]

        em = discord.Embed(title=content, description=f"\n[Jump]({jump_url})", color=0x96c8da)
        em.add_field(name="When", value=f"{human_time.timedelta(datetime.datetime.utcnow(), when=timer.created_at)} ago")
        await channel.send(content=user.mention, embed=em)

def setup(bot):
    bot.add_cog(Timers(bot))
