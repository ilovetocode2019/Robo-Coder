from discord.ext import commands
from discord.ext import menus
import discord

from datetime import datetime as d
import humanize
import dateparser

import inspect
import os
import asyncio
import functools
import aiohttp

from PIL import Image
from io import BytesIO

import io
import re
import zlib
from bs4 import BeautifulSoup

from .utils import custom

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    
    
async def average_image_color(avatar_url, loop, session=None):
    session = session or aiohttp.ClientSession()
    async with session.get(str(avatar_url)) as resp:
        data = await resp.read()
        image = BytesIO(data)

    partial = functools.partial(Image.open, image)
    img = await loop.run_in_executor(None, partial)

    partial = functools.partial(img.resize, (1, 1))
    img2 = await loop.run_in_executor(None, partial)

    partial = functools.partial(img2.getpixel, (0, 0))
    color = await loop.run_in_executor(None, partial)

    return(discord.Color(int("0x{:02x}{:02x}{:02x}".format(*color), 16)))

class Tools(commands.Cog):
    """Tools for discord."""
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="source", descriptin="Get source code for a specified command", usage="(command)")
    async def sourcecode(self, ctx, *, command=None):
        source_url = "https://github.com/ilovetocode2019/Robo-Coder"
        branch = "master"

        if command is None:
            return await ctx.send(source_url)
        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                return await ctx.send('Could not find command.')

            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            branch = 'master'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)


    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        await ctx.channel.trigger_typing()

        guild = ctx.guild
        
        try:
            color = await average_image_color(guild.icon_url, self.bot.loop)
        except:
            color = discord.Embed.Empty
        em = self.bot.build_embed(title=f"{guild.name} ({guild.id})", description="", color=color)
        
        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name="👑 Owner", value=guild.owner.mention)

        em.add_field(name="<:nitro:725730843930132560> Level", value=guild.premium_tier)

        em.add_field(name="🕒 Created at", value=f"{humanize.naturaldate(guild.created_at)} ({humanize.naturaltime(guild.created_at)})")

        em.add_field(name="🗣️ Channels", value=f"<:textchannel:725730867644858518> {str(len(guild.text_channels))} \N{BULLET} <:voicechannel:725730883872751666> {str(len(guild.voice_channels))}")

        status = {"online":0, "idle":0, "dnd":0, "offline":0}
        for member in guild.members:
            status[str(member.status)] += 1
        em.add_field(name="👪 Members", value=f" {len(guild.members)} total \n<:online:723954455292411974> {status['online']}\n<:idle:723954480957358142> {status['idle']}\n<:dnd:723954508396494878> {status['dnd']}\n<:offline:723954530072658010> {status['offline']}")

        await ctx.send(embed=em)

    @commands.command(name="userinfo", description="Get info on a user", usage="[member]", aliases=["ui"])
    @commands.guild_only()
    async def userinfo(self, ctx, *, user:discord.Member=None):
        await ctx.channel.trigger_typing()

        if not user:
            user = ctx.author

        badges = ""

        if user.public_flags.staff:
            badges += "<:staff:726131232534036572>"
        
        if user.public_flags.partner:
            badges += "<:partner:726131508330496170>"
        
        if user.public_flags.hypesquad:
            badges += "<:hypesquad:726131852427001887>"

        if user.public_flags.bug_hunter:
            badges += "<:bughunter:726132004604608553>"

        if user.public_flags.hypesquad_bravery:
            badges += "<:hypesquad_bravery:726132273082007659>"

        if user.public_flags.hypesquad_brilliance:
            badges += "<:hypesquad_brilliance:726132442343145583>"

        if user.public_flags.hypesquad_balance:
            badges += "<:hypesquad_balance:726132611084320879>"

        if user.public_flags.early_supporter:
            badges += "<:earlysupporter:726132986516471918>"

        if user.public_flags.verified_bot_developer:
            badges += "<:verified:726134370544386189>"

        try:
            color = await average_image_color(user.avatar_url, self.bot.loop)
        except:
            color = discord.Embed.Empty

        title = user.name
        if user.nick != None:
            title += f" ({user.nick})"
        title += f" - {user.id}"
        em = self.bot.build_embed(title=title, description=badges, color=color)
        
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n👑 This person owns the server"

        if user.bot:
            em.description += "\n🤖 This person is a bot"

        em.add_field(name="🕒 Created at", value=f"{humanize.naturaldate(user.created_at)} ({humanize.naturaltime(user.created_at)})")

        em.add_field(name="➡️ Joined at", value=f"{humanize.naturaldate(user.joined_at)} ({humanize.naturaltime(user.joined_at)})")

        for x in enumerate(sorted(ctx.guild.members, key=lambda x: x.joined_at)):
            if x[1] == user:
                em.add_field(name="👪 Join Position", value=x[0]+1)

        if len(user.roles) != 0:
            em.add_field(name="Roles", value=" ".join([role.mention for role in user.roles]))

        await ctx.send(embed=em)

    @commands.command(name="avatar", description="Get a users avatar")
    async def avatar(self, ctx, *, user:discord.Member=None):
        await ctx.channel.trigger_typing()

        if user == None:
            user = ctx.author

        try:
            color = await average_image_color(user.avatar_url, self.bot.loop)
        except:
            color = discord.Embed.Empty
        em = self.bot.build_embed(color=color)
        em.set_image(url=user.avatar_url)
        await ctx.send(embed=em)

    @commands.command(name="copy", description="Copies messages from the current channel to another", usage="[destination] [limit]")
    @commands.cooldown(1, 60)
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def copy(self, ctx, channel: discord.TextChannel, limit: int):
        if limit > 50:
            return await ctx.send("❌ You cannot copy over 50 messages")
        history = await ctx.channel.history(limit=limit+1).flatten()
        history = history[:-1]

        await ctx.send("Copying, This make take a moment")

        webhook = discord.utils.get((await channel.webhooks()), name="Copied Messages")
        if not webhook:
            webhook = await channel.create_webhook(name="Copied Messages")

        for message in history:
            try:
                await webhook.send(f"{discord.utils.escape_mentions(message.content)}\n{', '.join([x.url for x in message.attachments])}", embeds=message.embeds, username=message.author.display_name, avatar_url=message.author.avatar_url)
            except discord.HTTPException:
                pass

        await ctx.send(f"Finish copying messages into {channel.mention}")


def setup(bot):
    bot.add_cog(Tools(bot))