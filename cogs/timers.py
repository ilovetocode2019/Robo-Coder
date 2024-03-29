import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

from .utils import formats, human_time, menus

class RemindContextMenuModal(discord.ui.Modal, title="Remind Me"):
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How long do you want to be reminded about this in?",
        default="5 minutes"
    )

    def __init__(self, cog, message):
        super().__init__()
        self.cog = cog
        self.message = message

    async def on_submit(self, interaction):
        try:
            future_time = human_time.FutureTime(self.duration.value)
        except commands.BadArgument as exc:
            return await interaction.response.send_message(f"{str(exc)}", ephemeral=True)

        expires_at = future_time.time
        created_at = interaction.created_at

        timer = await self.cog.create_timer("reminder", [interaction.user.id, interaction.channel_id, self.message.jump_url, self.message.content or "..."], future_time.time, created_at)
        await interaction.response.send_message(f"Alright, I'll remind you about {self.message.jump_url} in {human_time.timedelta(timer.expires_at, when=timer.created_at)}.", ephemeral=True)

class SnoozeModal(discord.ui.Modal, title="Snooze Reminder"):
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="How long do you want to snooze for?",
        default="5 minutes"
    )

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction):
        try:
            future_time = human_time.FutureTime(self.duration.value)
        except commands.BadArgument as exc:
            return await interaction.response.send_message(f"{str(exc)}", ephemeral=True)

        expires_at = future_time.time
        created_at = interaction.created_at

        timer = await self.parent.cog.create_timer("reminder", [self.parent.timer.data[0], self.parent.timer.data[1], self.parent.timer.data[2], self.parent.timer.data[3]], future_time.time, created_at)

        self.parent.snooze.disabled = True
        await interaction.response.edit_message(view=self.parent)

        await interaction.followup.send(f"This timer has been snoozed for {human_time.timedelta(timer.expires_at, when=timer.created_at)}.", ephemeral=True)

class TimerView(discord.ui.View):
    def __init__(self, cog, timer):
        super().__init__()
        self.cog = cog
        self.timer = timer

        if timer.data[2]:
            self.add_item(discord.ui.Button(url=timer.data[2], label="Original Message"))

    @discord.ui.button(label="Snooze", style=discord.ButtonStyle.primary)
    async def snooze(self, interaction, button):
        await interaction.response.send_modal(SnoozeModal(self))

    async def interaction_check(self, interaction):
        if interaction.user.id != int(self.timer.data[0]):
            await interaction.response.send_message("You cannot snooze this timer, because you do not own it.", ephemeral=True)
            return False

        return True

    async def on_timeout(self):
        self.snooze.disabled = True
        await self.message.edit(view=self)

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

        self.current_timer = None
        self.timers_pending = asyncio.Event()
        self.timers_pending.set()
        self.loop = self.bot.loop.create_task(self.run_timers())

        self._remind_context_menu = app_commands.ContextMenu(name="Remind Later", callback=self.context_menu_remind)
        self.bot.tree.add_command(self._remind_context_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self._remind_context_menu.name, type=self._remind_context_menu.type)

    async def cog_unload(self):
        self.loop.cancel()

    @commands.hybrid_group(name="remind", description="Set a reminder", aliases=["timer", "reminder"], invoke_without_command=True)
    async def remind(self, ctx, *, reminder: human_time.TimeWithContent):
        content = reminder.content
        expires_at = reminder.time
        created_at = ctx.message.created_at

        timer = await self.create_timer("reminder", [ctx.author.id, ctx.channel.id, ctx.message.jump_url, content], expires_at, created_at)
        await ctx.send(f"Set a reminder for {human_time.timedelta(timer.expires_at, when=timer.created_at)}: {content}")

    async def context_menu_remind(self, interaction, message: discord.Message):
        await interaction.response.send_modal(RemindContextMenuModal(self, message))

    @remind.app_command.command(name="set", description="Set a reminder")
    @app_commands.describe(when="When you want to be reminded", text="What you want to be reminded")
    async def remind_set(self, interaction, when: human_time.TimeTransformer, text: str = "…"):
        created_at = interaction.created_at

        timer = await self.create_timer("reminder", [interaction.user.id, interaction.channel_id, None, text], when, created_at)
        await interaction.response.send_message(f"Set a reminder for {human_time.timedelta(timer.expires_at, when=timer.created_at)}: {text}")
        response = await interaction.original_response()

        # Update the timer to include the jump_url (from sending the response)
        query = """UPDATE timers
                   SET data=$1
                   WHERE timers.id=$2;
                """
        result = await self.bot.db.execute(query, [interaction.user.id, interaction.channel_id, response.jump_url, text], timer.id)

        self.restart_loop()

    @remind.command(name="list", description="List your reminders")
    async def remind_list(self, ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1
                   ORDER BY expires_at
                   LIMIT 10;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id))
        timers = [Timer(self.bot, **dict(timer)) for timer in timers]
        if not timers:
            return await ctx.send("You don't have any reminders.", ephemeral=True)

        em = discord.Embed(title="Reminders", description="\n", color=0x96c8da)
        for timer in timers:
            em.add_field(name=timer.id, value=f"{discord.utils.escape_markdown(timer.data[3])} in <t:{int(timer.expires_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>", inline=False)

        if len(timers) == 10:
            em.set_footer(text="Showing up to 10 reminders")
        else:
            em.set_footer(text=f"{formats.plural(len(timers)):reminder}")

        await ctx.send(embed=em)

    @remind.command(name="here", description="List your reminders in this channel")
    async def remind_here(self, ctx):
        query = """SELECT * FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1
                   AND data #>> '{1}' = $2
                   ORDER BY expires_at
                   LIMIT 10;
                """
        timers = await self.bot.db.fetch(query, str(ctx.author.id), str(ctx.channel.id))
        timers = [Timer(self.bot, **dict(timer)) for timer in timers]

        if not timers:
            return await ctx.send("You don't have any reminders in this channel.")

        em = discord.Embed(title="Reminders Here", description="\n", color=0x96c8da)
        for timer in timers:
            em.add_field(name=timer.id, value=f"{discord.utils.escape_markdown(timer.data[3])} in <t:{int(timer.expires_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>", inline=False)

        if len(timers) == 10:
            em.set_footer(text="Showing up to 10 reminders")
        else:
            em.set_footer(text=f"{formats.plural(len(timers)):reminder}")

        await ctx.send(embed=em)

    @remind.command(name="cancel", description="Cancel a reminder", aliases=["delete", "remove"])
    async def remind_cancel(self, ctx, reminder: int):
        query = """DELETE FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1 AND id = $2;
                """
        result = await self.bot.db.execute(query, str(ctx.author.id), reminder)

        if result == "DELETE 0":
            return await ctx.send("This reminder doesn't exist. Make sure you use a valid reminder ID.", ephemeral=True)

        if self.current_timer and self.current_timer.event == "reminder" and self.current_timer.id == reminder:
            # The timer running is the one we canceled, so we need to restart the loop
            self.restart_loop()

        await ctx.send("Reminder has been canceled.")

    @remind.command(name="clear", description="Clear all your reminders")
    async def remind_clear(self, ctx):
        query = """SELECT COUNT(*)
                   FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1;
                """
        result = await self.bot.db.fetchrow(query, str(ctx.author.id))

        if not result["count"]:
            return await ctx.send("No reminders to clear.", ephemeral=True)

        result = await menus.Confirm(f"Are you sure you want to clear {formats.plural(result['count']):reminder}?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        query = """DELETE FROM timers
                   WHERE event = 'reminder'
                   AND data #>> '{0}' = $1;
                """
        result = await self.bot.db.execute(query, str(ctx.author.id))

        if self.current_timer and self.current_timer.event == "reminder" and self.current_timer.data[0] == ctx.author.id:
            self.restart_loop()

        await ctx.send("All your reminders have been cleared.")

    @commands.command(name="reminders", description="List your reminders")
    async def reminders(self, ctx):
        await ctx.invoke(self.remind_list)

    async def create_timer(self, event, data, expires_at, created_at):
        expires_at = expires_at.replace(tzinfo=None)
        created_at = created_at.replace(tzinfo=None)

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
        channel = self.bot.get_channel(timer.data[1]) or await self.bot.fetch_channel(timer.data[1])
        created_at = timer.created_at
        content = timer.data[3]

        view = TimerView(self, timer)
        view.message = await channel.send(content=f"<@!{timer.data[0]}> <t:{int(created_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>: {content}", view=view)

async def setup(bot):
    await bot.add_cog(Timers(bot))
