from discord.ext import commands
import discord

from datetime import datetime
import traceback
import os
from datetime import datetime as d
import pickle
import json
import sys
import importlib
from discord.ext import menus

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')

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
    def __init__(self, data):
        self.cog = data
        super().__init__(data.get_commands(), per_page=10)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        em = discord.Embed(title=self.cog.qualified_name, description="", color=0x00ff00)

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
        return em


class MyHelpCommand(commands.HelpCommand):
    def get_command_signature(self, command):
        return '{0.clean_prefix}{1.qualified_name}{1.signature}'.format(self, command)
    async def send_bot_help(self, mapping):
        emojis = {"Conversation":"😃", "Mail":"📧", "Meta":"⚙️", "Moderation":"🚓", "Music":"🎵", "Tools":"🧰", "Fun":"🎡", "Games":"🎮", "Notes":"📓", "Reminders":"🗒️"}
        ctx = self.context
        bot = ctx.bot
        em = discord.Embed(title="Robo Coder Help", description="General bot help \n[arg]: Required argument \n(arg): Optional argument", color=0x00ff00)
        for name, cog in bot.cogs.items():
            if not cog.description:
                cog.description = ""
            if name not in ["Status", "Jishaku"]:
                em.add_field(name=emojis[name]+name, value=cog.description, inline=False)
        return await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot
        pages = menus.MenuPages(source=CogHelp(cog), clear_reactions_after=True)
        await pages.start(ctx)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot
        if command.hidden == True:
            return await ctx.send("🔒")
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

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot
        embed = discord.Embed(title=str(group.name), description="Command Group", color=0x00ff00)
        for command in group.commands:
            if command.description == None:
                commands.description = ""
            embed.add_field(name=command.name, value=command.description, inline=False)

        await ctx.send(embed=embed)




class Meta(commands.Cog):
    """Everything about the bot itself"""
    def __init__(self, bot):
        self.bot = bot 
        self._original_help_command = bot.help_command # Save the OG help command
        bot.help_command = MyHelpCommand() # Set the bot's help command to the custom one
        bot.help_command.cog = self # Set the cog for the helpcommand to this one

        if os.path.exists("prefixes.json"):
            with open("prefixes.json", "r") as f:
                self.bot.guild_prefixes = json.load(f)
        else:
            with open("prefixes.json", "w") as f:
                data = {}
                json.dump(data, f)
            self.bot.guild_prefixes = {}

    # @commands.Cog.listener("on_error")
    # async def _dm_dev(self, event):
    #     e = sys.exc_info()
    #     full =''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
    #     owner = self.bot.get_user(self.bot.owner_id)
    #     await owner.send(f"Error in {event}:```py\n{full}```")

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.Cog.listener("on_command_error")
    async def _send_error(self, ctx, e: commands.CommandError):
        error = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
        self.bot.previous_error = e
        if isinstance(e, commands.errors.CommandNotFound):
            return
        if isinstance(e, commands.errors.MissingPermissions):
            return
        if isinstance(e, commands.errors.CheckFailure):
            return
        if isinstance(e, commands.errors.NotOwner):
            return
        if isinstance(e, commands.errors.BadArgument):
            return await ctx.send("**:x: You provided a bad argument.** "
                                  "Make sure you are using the command correctly!")
        if isinstance(e, commands.errors.MissingRequiredArgument):
            return await ctx.send("**:x: Missing a required argument.** "
                                  "Make sure you are using the command correctly!")
        em = discord.Embed(title=":warning: Unexpected Error",
                           color=discord.Color.gold(),
                           timestamp=d.utcnow())
        description = ("An unexpected error has occured:"
                       f"```py\n{e}```\n The developer has been notified.")
        em.description = description
        em.set_footer(icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=em)

    def get_guild_prefixes(self, guild):
        if not guild:
            return "`c.` or when mentioned"
        guild = guild.id
        if str(guild) in self.bot.guild_prefixes.keys():
            prefixes = [f"`{p}`" for p in self.bot.guild_prefixes.get(str(guild))]
            prefixes.append("or when mentioned")
            return ", ".join(prefixes)
        return " ".join(self.bot.prefixes)
        

    @commands.command(name="add", description="add a prefix", usage="[prefix]")
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
                await ctx.send("That prefix does not exist. Try 'r! prefixes' to get a list of prefixes")
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


        
        
    @commands.command(name="reload", description="Reload an extension", aliases=['load'], usage="[cog]", hidden=True)
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
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not loaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not loaded.\n{traceback_data}")

        
    @commands.command(name = "ping", description = "Test the bots's latency")
    async def ping(self, ctx):
        start = datetime.timestamp(datetime.now())
        msg = await ctx.send("Pinging")

        ping = (datetime.timestamp(datetime.now()) - start) * 1000
        await msg.edit(content=f"Pong!\nOne message round-trip took {ping}ms.")        


    @commands.command(name="logout", description="Logout command", hidden=True)
    @commands.is_owner()
    async def logout(self, ctx):
        try:
            await self.bot.db.close()
        except:
            pass
        print("Logging out of Discord.")
        await ctx.send(":wave: Restarting. Please wait 15 seconds.")
        await self.bot.logout()

    @commands.command(name="restart", description="Restart command", hidden=True)
    @commands.is_owner()
    async def restart(self, ctx):
        try:
            await self.bot.db.close()
        except:
            pass
        print("Logging out of Discord and restarting")
        await ctx.send("Restarting...")
        os.startfile("bot.py")
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Meta(bot))