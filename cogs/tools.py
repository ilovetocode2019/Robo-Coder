from discord.ext import commands
import discord

from datetime import datetime as d
import inspect
import os
import asyncio

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    
    
    

class Tools(commands.Cog):
    """A bunch of tools you can use on your server."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="source", description="Get source code for my bot", usage="[command]")
    async def source(self, ctx, *, command: str = None):
        source_url = "https://github.com/ilovetocode2019/Robo-Coder"
        branch = "stable"
        if command is None:
            return await ctx.send(source_url)


        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = self.bot.get_command(command.replace(".", " "))
            if obj is None:
                return await ctx.send("Could not find command.")


            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename


        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace("\\", "/")
        else:
            location = module.replace(".", "/") + ".py"
            source_url = "https://github.com/Rapptz/discord.py"
            branch = "master"


        final_url = f"<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>"
        await ctx.send(final_url)

    @commands.command(name="purge", description="Delete a mass amount of meesages", usage="[amount]", hidden=True)
    @commands.is_owner()
    async def purge(self, ctx, *, arg):
        await ctx.send("Deleting " + str(arg) + " messages......")
        await asyncio.sleep(4)
        await ctx.channel.purge(limit=int(arg)+1)

    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild

        em = discord.Embed(title=guild.name, description="", color=0x00ff00)
        if not guild.large:
            em.description += "\nℹ️ This server is small"
        else:
            em.description += "\nℹ️ This server is big"

        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name="Owner", value=guild.owner.mention)

        em.add_field(name="ID", value=guild.id)

        em.add_field(name="Created at", value=str(guild.created_at))

        em.add_field(name="Channels", value=f"Text: {str(guild.member_count)}\nVoice: {str(len(guild.voice_channels))}")

        em.add_field(name="Members", value=len(guild.members))
        
        statuses = {"online":0, "idle":0, "dnd":0, "offline":0}
        for member in guild.members:
            statuses[str(member.status)] += 1
        em.add_field(name="Statues", value=f"Online {statuses['online']}\nIdle {statuses['idle']}\nDnd {statuses['dnd']}\nOffline {statuses['offline']}")

        await ctx.send(embed=em)
    @commands.command(name="userinfo", description="Get info on a user", usage="[member]")
    @commands.guild_only()
    async def userinfo(self, ctx, user:discord.Member=None):
        if not user:
            user = ctx.author

        if not user.nick:
            nick = ""
        else:
            nick = user.nick
        em = discord.Embed(title=user.name, description=nick, color=0x00ff00)
        
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n👑 This person owns the server"

        if user.bot:
            em.description += "\n🤖 This person is a bot"

        em.add_field(name="Created at", value=str(user.created_at))

        em.add_field(name="Joined at", value=str(user.joined_at))

        em.add_field(name="Roles", value=" ".join([role.mention for role in user.roles]))

        await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Tools(bot))