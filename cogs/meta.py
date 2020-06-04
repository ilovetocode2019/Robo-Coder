from discord.ext import commands
from discord.ext import tasks
from discord.ext import menus
import discord

import asyncio

from datetime import datetime
import traceback
import os
from datetime import datetime as d
import random
import pickle
import json
import sys
import importlib

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')

def readable(seconds): 
    seconds = seconds % (24 * 3600) 
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
      
    return "%d hours, %02d minutes, and %02d seconds" % (hour, minutes, seconds)

def has_manage_guild():
    async def predicate(ctx):
        try:
            await commands.has_guild_permissions(manage_guild=True).predicate(ctx)
            permissions = True
        except commands.errors.MissingPermissions:
            permissions = False
        return (
            ctx.author.id in ctx.bot.owner_ids
            or permissions
        )
    return commands.check(predicate)

class CogHelp(menus.ListPageSource):
    def __init__(self, data, bot):
        self.cog = data
        self.bot = bot
        super().__init__(data.get_commands(), per_page=20)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page

        if not self.cog.description:
            cogdescription = ""
        else:
            cogdescription = self.cog.description
        em = discord.Embed(title=self.cog.qualified_name, description=cogdescription+"\n", color=0x00ff00)

        for i, command in enumerate(entries, start=offset):
            if command.hidden != True:
                if not command.usage:
                    usage = ""
                else:
                    usage = f"{command.usage}"

                if not command.description:
                    description = "No desciption"
                else:
                    description = command.description

                if not command.aliases:
                    aliases = ""
                else:
                    aliases = "("+', '.join(command.aliases)+")"

                em.description += f"\n{command.name} {usage} - {description} {aliases}"

                if isinstance(command, commands.Group):
                    for subcommand in command.commands:
                        if not subcommand.usage:
                            usage = ""
                        else:
                            usage = f"{subcommand.usage}"

                        if not subcommand.description:
                            description = "No desciption"
                        else:
                            description = subcommand.description

                        if not subcommand.aliases:
                            aliases = ""
                        else:
                            aliases = "("+', '.join(subcommand.aliases)+")"

                        em.description += f"\n{command.name} {subcommand.name} {usage} - {description} {aliases}"
        
        em.set_footer(text = f"{self.bot.user.name}", icon_url=self.bot.user.avatar_url)
        return em


class MyHelpCommand(commands.HelpCommand):
    def get_command_signature(self, command):
        return '{0.clean_prefix}{1.qualified_name}{1.signature}'.format(self, command)
    async def send_bot_help(self, mapping):
        emojis = {"Conversation":"😃", "Meta":"⚙️", "Moderation":"🚓", "Music":"🎵", "Tools":"🧰", "Fun":"🎡", "Games":"🎮", "Notes":"📓", "Reminders":"🗒️"}
        ctx = self.context
        bot = ctx.bot
        em = discord.Embed(title=f"{bot.user.name} Help", description=f"General bot help. {bot.get_cog('Meta').get_guild_prefix(ctx.guild)}help [command] or {bot.get_cog('Meta').get_guild_prefix(ctx.guild)}help [category (first letter upercase)] for more specific help. \n[arg]: Required argument \n(arg): Optional argument", color=0x00ff00)
        for name, cog in bot.cogs.items():
            if not cog.description:
                cog.description = ""
            if name not in ["Music", "Jishaku"]:
                em.add_field(name=f"{emojis[name]} {name}", value=cog.description, inline=False)
        

        em.set_footer(text = f"{bot.user.name}", icon_url=bot.user.avatar_url)
        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        if cog.qualified_name in ["Jishaku"]:
            return
        ctx = self.context
        bot = ctx.bot
        pages = menus.MenuPages(source=CogHelp(cog, bot), clear_reactions_after=True)
        await pages.start(ctx)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot
        if command.hidden == True:
            return
        if not command.usage:
            usage = ""
        else:
            usage = command.usage

        embed = discord.Embed(title=str(command) + " " + usage, description=command.description, color=0x00ff00)
        if command.help != None:
            embed.add_field(name="Detailed Help:", value=command.help, inline=False)
        if command.aliases != []:
            embed.add_field(name="Aliases:", value=", ".join(command.aliases), inline=False)
        await ctx.send(embed=embed)


class Meta(commands.Cog):
    """Everything about the bot itself"""
    def __init__(self, bot):
        self.bot = bot

        self.activity.start()
        self._original_help_command = bot.help_command
        bot.help_command = MyHelpCommand()
        bot.help_command.cog = self

        if os.path.exists("prefixes.json"):
            with open("prefixes.json", "r") as f:
                self.bot.guild_prefixes = json.load(f)
        else:
            with open("prefixes.json", "w") as f:
                data = {}
                json.dump(data, f)
            self.bot.guild_prefixes = {}

    def cog_unload(self):
        self.activity.cancel()
        self.bot.help_command = self._original_help_command

    @commands.Cog.listener("on_command_error")
    async def _send_error(self, ctx, e: commands.CommandError):
        error = "".join(traceback.format_exception(type(e), e, e.__traceback__, 1))
        print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

        if isinstance(e, discord.ext.commands.errors.CheckFailure):
            return
        elif isinstance(e, discord.ext.commands.errors.MissingPermissions):
            return await ctx.send(":x: I don't have the permissions to do this") 
        elif isinstance(e, discord.ext.commands.errors.MissingRequiredArgument):
            return await ctx.send(":x: You are missing a required argument")
        elif isinstance(e, discord.ext.commands.errors.BadArgument):
            return await ctx.send(":x: You are giving a bad argument")
        elif isinstance(e, discord.ext.commands.errors.CommandNotFound):
            return

        em = discord.Embed(title=":warning:",
                           color=0xff0000,
                           timestamp=d.utcnow())
        em.description = f"```py\n{str(e)}```\n"
        msg = await ctx.send(embed=em)

        if ctx.author.id in self.bot.owner_ids:
            checkmark = await msg.add_reaction("👀")
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) == "👀"
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                if str(reaction.emoji) == "👀":
                    await user.send(f"```python\n{''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))}```")              
            except asyncio.TimeoutError:
                await msg.remove_reaction("👀", self.bot.user)

    @commands.Cog.listener("on_message")
    async def detect_mention(self, msg):
        if msg.content == f"<@!{self.bot.user.id}>":
            await msg.channel.send(f"Hi. For help use {self.get_guild_prefix(msg.guild)}help.")

    def get_guild_prefix(self, guild):
        if not guild:
            return "r!"
        return self.bot.guild_prefixes[str(guild.id)][0]

    @commands.command(name="add", description="add a prefix", usage="[prefix]")
    @commands.guild_only()
    @has_manage_guild()
    async def add(self, ctx, *, arg):
        #global self.bot.guild_prefixes
        if not str(ctx.guild.id) in self.bot.guild_prefixes.keys():
            self.bot.guild_prefixes[str(ctx.guild.id)] = [arg]
        else:
            self.bot.guild_prefixes[str(ctx.guild.id)] = self.bot.guild_prefixes[str(ctx.guild.id)] + [arg]
        with open("prefixes.json", "w") as f:
            json.dump(self.bot.guild_prefixes, f)
        await ctx.send("Added prefix: " + arg)
    
    @commands.command(name="remove", description="remove prefix", usage="[prefix]")
    @commands.guild_only()
    @has_manage_guild()
    async def remove(self, ctx, *, arg):
        #global self.bot.guild_prefixes
        if str(ctx.guild.id) in self.bot.guild_prefixes.keys():
            if arg in self.bot.guild_prefixes[str(ctx.guild.id)]:
                self.bot.guild_prefixes[str(ctx.guild.id)].remove(arg)
                await ctx.send("Removed prefix: " + arg)
            else:
                await ctx.send(f"That prefix does not exist. Try '{self.get_guild_prefix(ctx.guild)}prefixes' to get a list of prefixes")
            if self.bot.guild_prefixes[str(ctx.guild.id)] == []:
                del self.bot.guild_prefixes[str(ctx.guild.id)]
            with open("prefixes.json", "w") as f:
                json.dump(self.bot.guild_prefixes, f)
        else:
            await ctx.send("No custom prefies")

    @commands.command(name="prefixes", description="veiw a list of prefixes")
    @commands.guild_only()
    async def prefixes(self, ctx):
        #if str(ctx.guild.id) in self.bot.guild_prefixes.keys():
        server_prefixes = self.bot.guild_prefixes[str(ctx.guild.id)]
        await ctx.send("prefixes: " + ", ".join(self.bot.guild_prefixes[str(ctx.guild.id)]))        
        
    @commands.command(name="reload", description="Reload an extension", usage="[cog]", hidden=True)
    @commands.is_owner()
    async def _reload(self, ctx, cog="all"):
        if cog == "all":
            msg = ""

            for ext in self.bot.cogs_to_add:
                try:
                    self.bot.reload_extension(ext)
                    msg += f"**:repeat: Reloaded** `{ext}`\n\n"
                    print(f"Extension '{cog.lower()}' successfully reloaded.")

                except Exception as e:
                    traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
                    msg += (f"**:warning: Extension `{ext}` not loaded.**\n"
                            f"```py\n{traceback_data}```\n\n")
                    print(f"Extension 'cogs.{cog.lower()}' not loaded.\n"
                                     f"{traceback_data}")
            return await ctx.send(msg)

        try:
            self.bot.reload_extension(cog.lower())
            await ctx.send(f"**:repeat: Reloaded** `{cog.lower()}`")
            print(f"Extension '{cog.lower()}' successfully reloaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not reloaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not reloaded.\n{traceback_data}")

    @commands.command(name="load", description="Load an extension", usage="[cog]", hidden=True)
    @commands.is_owner()
    async def _load(self, ctx, cog):
        try:
            self.bot.load_extension(cog.lower())
            await ctx.send(f"**:white_check_mark: Loaded** `{cog.lower()}`")
            print(f"Extension '{cog.lower()}' successfully loaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not loaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not loaded.\n{traceback_data}")

    @commands.command(name="unload", description="Unload an extension", usage="[cog]", hidden=True)
    @commands.is_owner()
    async def _unload_cog(self, ctx, cog):
        try:
            self.bot.unload_extension(cog)
            await ctx.send(f"**:x: Unloaded extension ** `{cog}`")
            print(f"Extension '{cog}' successfully unloaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not unloaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog}' not unloaded.\n{traceback_data}")

        

    @commands.command(name="log", description="Get the log for the bot", hidden=True)
    @commands.is_owner()
    async def log(self, ctx):
        file = discord.File("coder.log", filename="log.txt")
        await ctx.send(content="Here is the log", file=file)

        
    @commands.command(name = "ping", description = "Test the bots's latency")
    async def ping(self, ctx):
        start = datetime.timestamp(datetime.now())
        msg = await ctx.send("Pinging")

        ping = (datetime.timestamp(datetime.now()) - start) * 1000
        await msg.edit(content=f"Pong!\nOne message round-trip took {ping}ms.")

    @commands.group(name="uptime", description="Get the uptime", invoke_without_command=True)
    async def uptime(self, ctx):
        uptime = datetime.now()-self.bot.startup_time
        await ctx.send(f"I have been up for {uptime.days} days, {readable(uptime.seconds)}")      

    @uptime.command(name="overall", description="Get the overall bot uptime")
    async def overalluptime(self, ctx):
        cursor = await self.bot.db.execute("SELECT * FROM Events")
        rows = await cursor.fetchall()
        rows = list(rows)
        record_start = rows[0][1]
        total_uptime = 0
        counter = 0
        now = datetime.now()
        now = datetime.timestamp(now)

        for row in rows:
            if row[0] == "Online":
                if len(rows) > counter+1:
                    next_time = rows[counter+1][1]
                else:
                    next_time = now
                total_uptime += next_time-row[1]
            counter += 1

        full_time = now-record_start
        await cursor.close()
        await ctx.send(f"I am up {(total_uptime/full_time)*100}% of the time")
    
    @commands.command(name="invite", description="Get a invite to add me to your server")
    async def invite(self, ctx):
        invite = discord.utils.oauth_url(self.bot.user.id, permissions=None, guild=None, redirect_uri=None)
        await ctx.send(f"<{invite}>")

    @commands.command(name="github", description="Look at my repository", usage="[command]")
    async def github(self, ctx, *, command: str = None):
        source_url = "https://github.com/ilovetocode2019/Robo-Coder"
        branch = "stable"
        await ctx.send(f"{source_url}/tree/{branch}")


    @commands.command(name="logout", description="Logout command", hidden=True)
    @commands.is_owner()
    async def logout(self, ctx):
        now = datetime.now()
        timestamp = datetime.timestamp(now)
        await self.bot.db.execute(f"INSERT INTO Events('Event', 'Time') VALUES ('Offline', '{timestamp}');")
        await self.bot.db.commit()

        try:
            await self.bot.db.close()
        except:
            pass
        print("Logging out of Discord.")
        await ctx.send(":wave: Logging out.")
        await self.bot.logout()

    @commands.command(name="restart", description="Restart command", hidden=True)
    @commands.is_owner()
    async def restart(self, ctx):
        now = datetime.now()
        timestamp = datetime.timestamp(now)
        await self.bot.db.execute(f"INSERT INTO Events('Event', 'Time') VALUES ('Offline', '{timestamp}');")
        await self.bot.db.commit()

        try:
            await self.bot.db.close()
        except:
            pass
        print("Logging out of Discord and restarting")
        await ctx.send("Restarting...")
        os.startfile("bot.py")
        await self.bot.logout()

    @tasks.loop(minutes=30)
    async def activity(self):
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.playing, name=random.choice(["Minecraft", "Rocket League", "Visual Studio Code", "Celeste", "INSIDE", "Portal", "Portal 2", None])))



def setup(bot):
    bot.add_cog(Meta(bot))