import discord
from discord.ext import commands
import asyncio

import matplotlib.pyplot as plt
from io import BytesIO

from datetime import datetime as d
import functools

def draw_pie(status):
    total = status["online"] + status["idle"] + status["dnd"] + status["offline"]
    labels = []
    sizes = []
    colors = []
    for x in status:
        if status[x]/total*100 > 0:
            labels.append(x)
            sizes.append(status[x]/total*100)
            colors.append({"online":"green", "idle":"yellow", "dnd":"red", "offline":"gray"}[x])
    
    plt.pie(sizes, labels=[f"{round(size, 2)}%" for size in sizes], colors=colors, startangle=140)

    legend = []
    counter = 0
    for x in range(len(colors)):
        legend.append(f"{labels[x]} ({round(sizes[x], 2)}%)")
    plt.legend(legend, loc="best")
    plt.axis('equal')
    f = BytesIO()
    plt.savefig(f, format="png")
    f.seek(0)
    plt.close()
    return f


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_member_update")
    async def on_member_update(self, before, after):
        if before.status != after.status:
            timestamp = d.now().timestamp()
            await self.bot.db.execute(f'''INSERT INTO Status_Updates(Userid, Status, Time) VALUES ($1, $2, $3)''', str(before.id), str(after.status), int(timestamp))

    @commands.Cog.listener("on_connect")
    async def on_connect(self):
        for user in self.bot.get_all_members():
            rows = rows = await self.bot.db.fetch(f"SELECT Status, Time FROM Status_Updates WHERE Status_Updates.Userid='{user.id}';")
            if len(rows) != 0:
                if rows[-1][0] != str(user.status):
                    timestamp = datetime.now().timestamp()
                    await self.bot.db.execute(f'''INSERT INTO Status_Updates(Userid, Status, Time) VALUES ($1, $2, $3)''', str(user.id), str(user.status), int(timestamp))

    @commands.command(name="status", description="Get an overall status of a user", usage="[user]")
    async def status(self, ctx, *, user: discord.Member=None):
        if not user:
            user = ctx.author

        rows = await self.bot.db.fetch(f"SELECT Status, Time FROM Status_Updates WHERE Status_Updates.Userid='{user.id}';")
        if len(rows) == 0:
            rows = [[str(user.status), int(d.now().timestamp())]]
            await self.bot.db.execute(f'''INSERT INTO Status_Updates(Userid, Status, Time) VALUES ($1, $2, $3)''', str(user.id), str(user.status), int(d.now().timestamp()))
        counter = 0
        status = {"online":0, "idle":0, "dnd":0, "offline":0}
        for row in rows:
            if len(rows)-1 > counter:
                status[row[0]] += rows[counter+1][1]-row[1]
            else:
                status[str(user.status)] += d.now().timestamp()-row[1]

            counter += 1
        
        loop = self.bot.loop
        partial = functools.partial(draw_pie, status)
        data = await loop.run_in_executor(None, partial)

        await ctx.send(file=discord.File(fp=data, filename="test.png"))

def setup(bot):
    bot.add_cog(Status(bot))