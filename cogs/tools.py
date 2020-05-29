from discord.ext import commands
import discord

from datetime import datetime as d
import inspect
import os
import asyncio
import aiohttp

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    
    

class Tools(commands.Cog):
    """A bunch of tools you can use on your server."""
    def __init__(self, bot):
        self.bot = bot
    
    @commands.cooldown(1, 10)
    @commands.command(name="source", descriptin="Get source code for a specified command", usage="[command]")
    async def sourcecode(self, ctx, *, command_name: str):
        command = self.bot.get_command(command_name)
        if not command:
            return await ctx.send(f"Couldn't find command `{command_name}`.")

        try:
            source_lines, _ = inspect.getsourcelines(command.callback)
        except (TypeError, OSError):
            return await ctx.send(f"Was unable to retrieve the source for `{command}` for some reason.")

        source_lines = ''.join(source_lines)
        async with aiohttp.ClientSession() as session:
            async with session.post('https://hastebin.com/documents', data=str(source_lines).encode("utf-8")) as post:
                post_json = (await post.json())

        await ctx.send(f"https://hastebin.com/{post_json['key']}")


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
        
        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name="Owner", value=guild.owner.mention)

        em.add_field(name="ID", value=guild.id)

        em.add_field(name="Created at", value=str(guild.created_at))

        em.add_field(name="Channels", value=f"Text: {str(guild.member_count)}\nVoice: {str(len(guild.voice_channels))}")

        em.add_field(name="Members", value=len(guild.members))
        
        status = {"online":0, "idle":0, "dnd":0, "offline":0}
        for member in guild.members:
            status[str(member.status)] += 1
        em.add_field(name="Status List", value=f"Online {status['online']}\nIdle {status['idle']}\nDnd {status['dnd']}\nOffline {status['offline']}")

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