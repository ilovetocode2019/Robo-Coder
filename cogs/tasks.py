import discord
from discord.ext import commands, tasks

import datetime
import asyncio

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True
        self.loop.start()

    def cog_unload(self):
        self.loop.cancel()

    async def dispatch_task(self, task):
        till = task["time"]-datetime.datetime.utcnow()
        if till.days == 0:
            await asyncio.sleep(till.seconds)
        self.bot.dispatch(f"{task['task']}_task", task)

        query = """DELETE FROM tasks
                    WHERE tasks.id=$1;
                """
        await self.bot.db.execute(query, task["id"])

    @tasks.loop(seconds=30)
    async def loop(self):
        all_tasks = await self.bot.db.fetch("SELECT * FROM tasks;")
        for task in all_tasks:
            till = task["time"]-datetime.datetime.utcnow()
            if (till.seconds < 30 and till.days == 0) or (till.days < 0):
                self.bot.loop.create_task(self.dispatch_task(task))

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Tasks(bot))
