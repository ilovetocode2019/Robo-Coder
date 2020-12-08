import discord
from discord.ext import commands

import humanize
import inspect
import os
import functools
import io
import re
import zlib
import json
import unicodedata
import collections
import typing
import datetime

from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

from .utils import human_time

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
    """Tools for Discord."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":toolbox:"

    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        await ctx.channel.trigger_typing()

        guild = ctx.guild
        
        try:
            color = await average_image_color(guild.icon_url, self.bot.loop, self.bot.session)
        except:
            color = discord.Embed.Empty
        em = discord.Embed(title=f"{guild.name} ({guild.id})", description="", color=color)
        
        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name="👑 Owner", value=guild.owner.mention)

        em.add_field(name="<:nitro:725730843930132560> Level", value=guild.premium_tier)

        em.add_field(name="🕒 Created at", value=f"{humanize.naturaldate(guild.created_at)} ({humanize.naturaltime(guild.created_at)})")

        em.add_field(name="🗣️ Channels", value=f"<:textchannel:725730867644858518> {str(len(guild.text_channels))} \N{BULLET} <:voicechannel:725730883872751666> {str(len(guild.voice_channels))}")

        em.add_field(name="👪 Members", value=f"{len(guild.members)} ({len([x for x in guild.members if x.bot])} bots)")
        await ctx.send(embed=em)

    @commands.command(name="userinfo", description="Get info on a user", aliases=["ui", "whois"])
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
            color = await average_image_color(user.avatar_url, self.bot.loop, session=self.bot.session)
        except:
            color = discord.Embed.Empty

        title = user.name
        if user.nick != None:
            title += f" ({user.nick})"
        title += f" - {user.id}"
        em = discord.Embed(title=title, description=badges, color=color)
        
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n👑 This person owns the server"

        if user.bot:
            em.description += "\n🤖 This user is a bot"

        em.add_field(name="🕒 Created at", value=f"{humanize.naturaldate(user.created_at)} ({humanize.naturaltime(user.created_at)})")

        em.add_field(name="➡️ Joined at", value=f"{humanize.naturaldate(user.joined_at)} ({humanize.naturaltime(user.joined_at)})")

        for x in enumerate(sorted(ctx.guild.members, key=lambda x: x.joined_at)):
            if x[1] == user:
                em.add_field(name="👪 Join Position", value=x[0]+1)

        if len(user.roles) != 0:
            em.add_field(name="Roles", value=" ".join([role.mention for role in user.roles if not role.is_default()]))

        await ctx.send(embed=em)

    @commands.command(name="avatar", description="Get a users avatar")
    async def avatar(self, ctx, *, user:discord.Member=None):
        await ctx.channel.trigger_typing()

        if user == None:
            user = ctx.author

        try:
            color = await average_image_color(user.avatar_url, self.bot.loop, self.bot.session)
        except:
            color = discord.Embed.Empty
        em = discord.Embed(color=color)
        em.set_author(name=user.display_name, icon_url=user.avatar_url)
        em.set_image(url=user.avatar_url)
        await ctx.send(embed=em)

    @commands.command(name="charinfo", decription="Get info on a charecter")
    async def charinfo(self, ctx, *, text):
        if len(text) > 20:
            return await ctx.send("Your text must be shorter than 20 charecters")

        info = []
        for charecter in text:
            digit = f'{ord(charecter):x}'
            name = unicodedata.name(charecter, "Name not found")
            info.append(f'`\\U{digit:>08}`: {name} - {charecter} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>')
        await ctx.send("\n".join(info))

    @commands.command(name="poll", description="Create a poll")
    @commands.guild_only()
    async def poll(self, ctx, title = None, time: typing.Optional[human_time.TimeConverter] = None, *options):
        possible_reactions = [
            "\N{REGIONAL INDICATOR SYMBOL LETTER A}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER B}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER C}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER D}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER E}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER F}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER G}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER H}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER I}",
            "\N{REGIONAL INDICATOR SYMBOL LETTER J}",
        ]

        Option = collections.namedtuple("Option", ["emoji", "text"])

        if not time:
            time = datetime.datetime.utcnow()+datetime.timedelta(days=1)

        if not title:
            options = []

            check = lambda message: message.channel == ctx.author.dm_channel and message.author == ctx.author
            await ctx.author.send("What is the title of the poll?")

            message = await self.bot.wait_for("message", check=check)
            title = message.content

            await ctx.author.send("How long would you like the poll to last")
            message = await self.bot.wait_for("message", check=check)
            try:
                time = await human_time.TimeConverter().convert(ctx, message.content)
            except commands.BadArgument:
                return await ctx.author.send(":x: That is not a valid time")

            await ctx.author.send("Send me up to 10 poll options. Type `done` to send the poll")
            while len(options) < len(possible_reactions):
                message = await self.bot.wait_for("message", check=check)
                if message.content == "done":
                    break
                elif message.content == "abort":
                    return await ctx.author.send("Aborted")

                args = message.content.split(" ")
                if len(args) == 1:
                    options.append(Option(None, message.content))
                    await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
                else:
                    emoji = args[0]
                    text = " ".join(args[1:])
                    if emoji in [option.emoji for option in options]:
                        await message.add_reaction("\N{CROSS MARK}")
                        await ctx.author.send(":x: You already used that emoji", delete_after=5)
                    elif text in [option.text for option in options]:
                        await message.add_reaction("\N{CROSS MARK}")
                        await ctx.author.send(":x: You already added that option", delete_after=5)
                    else:
                        if emoji in self.bot.default_emojis:
                            options.append(Option(emoji, text))
                        else:
                            options.append(Option(None, message.content))
                        await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

        else:
            options = [Option(None, text) for text in options]

        if len(options) > len(possible_reactions):
            raise commands.BadArgument(f"You cannot have more then {len(possible_reactions)} options")

        description = ""
        reactions = []
        for counter, option in enumerate(options):
            if option.emoji:
                emoji = option.emoji
            else:
                emoji = possible_reactions[counter]

            description += f"\n{emoji} {option.text}"
            reactions.append(emoji)

        em = discord.Embed(title=title, description=description)
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        message = await ctx.send(embed=em)

        for reaction in reactions:
            await message.add_reaction(reaction)

def setup(bot):
    bot.add_cog(Tools(bot))
