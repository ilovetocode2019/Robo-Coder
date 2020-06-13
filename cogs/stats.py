from discord.ext import commands
from discord.ext import tasks
import discord

from datetime import datetime

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queries = []
        self.log_commands.start()

    def cog_unload(self):
        self.log_commands.cancel()

    @commands.Cog.listener("on_command_completion")
    @commands.guild_only()
    async def on_command(self, ctx):
        self.queries.append(("INSERT INTO Commands(Userid, Guildid, Command, Time) Values($1, $2, $3, $4)", str(ctx.author.id), str(ctx.guild.id), str(ctx.command), int(datetime.timestamp(datetime.now()))))
    
    @commands.command(name="stats", description="Look at command usage for the current guild")
    @commands.guild_only()
    async def stats(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT * FROM Commands WHERE Commands.Guildid='{ctx.guild.id}';")
        users = {}
        for row in rows:
            if int(row[0]) not in users:
                users[int(row[0])] = 1
            else:
                users[int(row[0])] += 1

        commands_used = {}
        for row in rows:
            if row[2] not in commands_used:
                commands_used[row[2]] = 1
            else:
                commands_used[row[2]] += 1


        em = discord.Embed(title="Stats", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        em.add_field(name="Top Commands Used", value="\n".join([f"{x} ({commands_used[x]})" for x in reversed(sorted(commands_used, key=commands_used.get))][:5]))
        em.add_field(name="Top Command Users", value="\n".join([f"{str(ctx.guild.get_member(x))} ({users[x]})" for x in reversed(sorted(users, key=users.get))][:5]))
        await ctx.send(embed=em)

    @tasks.loop(seconds=15)
    async def log_commands(self):
        for query in self.queries:
            await self.bot.db.execute(*query)
        self.queries = []

def setup(bot):
    bot.add_cog(Stats(bot))