from discord.ext import commands
from discord.ext import tasks
import discord

from datetime import datetime

from .utils import time

import os
import codecs
import pathlib

def get_lines_of_code(comments=False):
    total_lines = 0
    file_amount = 0
    for path, subdirs, files in os.walk("."):
        if "venv" in subdirs:
            subdirs.remove("venv")
        if "env" in subdirs:
            subdirs.remove("env")
        if "venv-old" in subdirs:
            subdirs.remove("venv-old")
        for name in files:
            if name.endswith(".py"):
                file_amount += 1
                f = open(str(pathlib.PurePath(path, name)), encoding="utf-8")
                total_lines += len(f.readlines())
                f.close()
    return f"I am made of {total_lines} lines of code spread out over {file_amount} files"

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queries = []
        self.log_commands.start()

    def cog_unload(self):
        self.log_commands.cancel()

    @commands.Cog.listener("on_command_completion")
    async def on_command(self, ctx):
        if not ctx.guild:
            self.queries.append(("INSERT INTO Commands(Userid, Guildid, Command, Time) Values($1, $2, $3, $4)", str(ctx.author.id), "@me", str(ctx.command), int(datetime.timestamp(datetime.utcnow()))))
        else:
            self.queries.append(("INSERT INTO Commands(Userid, Guildid, Command, Time) Values($1, $2, $3, $4)", str(ctx.author.id), str(ctx.guild.id), str(ctx.command), int(datetime.timestamp(datetime.utcnow()))))
    
    @commands.group(name="stats", description="Look at command usage for the current guild", invoke_without_command=True)
    @commands.guild_only()
    async def stats_group(self, ctx, *, guild_search=None):
        new_guild = ctx.guild
        if ctx.author.id == self.bot.owner_id:
            if guild_search != None:
                result = discord.utils.get(self.bot.guilds, name=guild_search)
                if result != None:
                    new_guild = result

        rows = await self.bot.db.fetch(f"SELECT * FROM commands WHERE commands.guildid='{new_guild.id}';")
        if not len(rows):
            return await ctx.send("No commands have been used")
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

        
        timestamp = datetime.utcnow().timestamp()-86400
        
        users_today = {}
        for row in rows:
            if row[3] > timestamp:
                if int(row[0]) not in users_today:
                    users_today[int(row[0])] = 1
                else:
                    users_today[int(row[0])] += 1

        commands_used_today = {}
        for row in rows:
            if row[3] > timestamp:
                if row[2] not in commands_used_today:
                    commands_used_today[row[2]] = 1
                else:
                    commands_used_today[row[2]] += 1


        em = discord.Embed(title="Stats", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        em.add_field(name="Top Commands Used", value="\n".join([f"{x} ({commands_used[x]})" for x in reversed(sorted(commands_used, key=commands_used.get))][:5]))
        
        if len(users_today) != 0:
            em.add_field(name="Top Commands Used Today", value="\n".join([f"{x} ({commands_used_today[x]})" for x in reversed(sorted(commands_used_today, key=commands_used_today.get))][:5]))
        
        em.add_field(name="Top Command Users", value="\n".join([f"{str(new_guild.get_member(x))} ({users[x]})" for x in reversed(sorted(users, key=users.get))][:5]))
        
        if len(commands_used_today) != 0:
            em.add_field(name="Top Command Users Today", value="\n".join([f"{str(new_guild.get_member(x))} ({users_today[x]})" for x in reversed(sorted(users_today, key=users_today.get))][:5]))

        await ctx.send(embed=em)
    
    @stats_group.command(name="global")
    @commands.is_owner()
    async def stats_global(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT * FROM Commands")
        usage = {"Other":0, "DM":0}
        for row in rows:
            if row[1] == "@me":
                usage["DM"] += 1
            elif self.bot.get_guild(int(row[1])) != None:
                if ctx.author.id in [x.id for x in self.bot.get_guild(int(row[1])).members]:
                    guild_name = self.bot.get_guild(int(row[1])).name
                    if guild_name in usage:
                        usage[guild_name] += 1
                    else:
                        usage[guild_name] = 1
                
                else:
                    usage["Other"] += 1

        await ctx.send("\n".join([f"{x} ({usage[x]})" for x in reversed(sorted(usage, key=usage.get))]))
    
    @commands.command(name="about", description="Info about me", aliases=["info"])
    async def about(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            em = discord.Embed(title="Stats")
        else:
            em = discord.Embed(title="Stats", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        lines = 0
        em.add_field(name="Code", value=get_lines_of_code())
        uptime = datetime.now()-self.bot.startup_time
        em.add_field(name="Uptime", value=f"{uptime.days} days, {time.readable(uptime.seconds)}")
        em.add_field(name="Latency", value=f"{self.bot.latency}ms")
        await ctx.send(embed=em)

    @tasks.loop(seconds=15)
    async def log_commands(self):
        for query in self.queries:
            await self.bot.db.execute(*query)
        self.queries = []

def setup(bot):
    bot.add_cog(Stats(bot))