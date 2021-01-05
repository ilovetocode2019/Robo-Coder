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

from PIL import Image
from io import BytesIO

from .utils import formats

class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":toolbox:"

    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild

        async with ctx.typing():
            if not guild.chunked:
                await guild.chunk(cache=True)

            try:
                color = await self.average_image_color(guild.icon_url_as(format="png"))
            except:
                color = discord.Embed.Empty

        em = discord.Embed(color=color)
        em.set_author(name=f"{guild.name} ({guild.id})", icon_url=ctx.guild.icon_url)
        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name=":crown: Owner", value=guild.owner.mention)
        em.add_field(name=":clock3: Created at", value=f"{humanize.naturaldate(guild.created_at)} ({humanize.naturaltime(guild.created_at)})")
        em.add_field(name="<:nitro:725730843930132560> Nitro Boosts", value=guild.premium_tier)
        bots = len([member for member in guild.members if member.bot])
        em.add_field(name=":earth_americas: Region", value=str(guild.region).upper().replace("-", " "))
        em.add_field(name=":speaking_head: Channels", value=f"<:textchannel:725730867644858518> {str(len(guild.text_channels))} \N{BULLET} <:voicechannel:725730883872751666> {str(len(guild.voice_channels))}")
        em.add_field(name=":family: Members", value=f"{len(guild.members)} ({formats.plural(bots):bot})")

        static_emojis = len([emoji for emoji in guild.emojis if not emoji.animated])
        static_emojis_percentage = int((static_emojis/guild.emoji_limit)*100)
        static_text = f"{static_emojis}/{guild.emoji_limit} ({static_emojis_percentage}%)"
        animated_emojis = len([emoji for emoji in guild.emojis if emoji.animated])
        animated_emojis_percentage = int((animated_emojis/guild.emoji_limit)*100)
        animated_text = f"{animated_emojis}/{guild.emoji_limit} ({animated_emojis_percentage}%)"
        emoji_percentage = int((len(guild.emojis)/(guild.emoji_limit*2))*100)
        em.add_field(name=":pencil: Emojis", value=f"Static: {static_text} \nAnimated: {animated_text} \nTotal: {len(guild.emojis)}/{guild.emoji_limit*2} ({emoji_percentage}%)")
        em.add_field(name=":bookmark: Roles", value=str(len(guild.roles)))

        await ctx.send(embed=em)

    @commands.command(name="userinfo", description="Get info on a user", aliases=["ui", "whois"])
    @commands.guild_only()
    async def userinfo(self, ctx, *, user: discord.Member = None):
        if not user:
            user = ctx.author

        pubilic_flags_mapping = {
        discord.UserFlags.staff: "<:staff:726131232534036572>",
        discord.UserFlags.partner: "<:partner:726131508330496170>",
        discord.UserFlags.hypesquad: "<:hypesquad:726131852427001887>",
        discord.UserFlags.bug_hunter: "<:bughunter:726132004604608553>",
        discord.UserFlags.hypesquad_bravery: "<:hypesquad_bravery:726132273082007659>",
        discord.UserFlags.hypesquad_brilliance: "<:hypesquad_brilliance:726132442343145583>",
        discord.UserFlags.hypesquad_balance: "<:hypesquad_balance:726132611084320879>",
        discord.UserFlags.early_supporter: "<:earlysupporter:726132986516471918>",
        discord.UserFlags.verified_bot_developer: "<:verified:726134370544386189>",
        }

        badges = ""
        for flag in user.public_flags.all():
            emoji = pubilic_flags_mapping.get(flag)
            if emoji:
                badges += emoji

        async with ctx.typing():
            try:
                color = await self.average_image_color(user.avatar_url_as(format="png"))
            except:
                color = discord.Embed.Empty

        em = discord.Embed(description=badges, color=color)
        em.set_author(name=f"{user} {f'({user.nick})' if user.nick else ''} - {user.id}", icon_url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n:crown: This person owns the server"
        if user.bot:
            em.description += "\n:robot: This user is a bot"

        em.add_field(name=":clock3: Created at", value=f"{humanize.naturaldate(user.created_at)} ({humanize.naturaltime(user.created_at)})")
        em.add_field(name=":arrow_right: Joined at", value=f"{humanize.naturaldate(user.joined_at)} ({humanize.naturaltime(user.joined_at)})")

        for x in enumerate(sorted(ctx.guild.members, key=lambda x: x.joined_at)):
            if x[1] == user:
                em.add_field(name=":family: Join Position", value=x[0]+1)
        if len(user.roles) > 1:
            em.add_field(name="Roles", value=" ".join([role.mention for role in reversed(user.roles) if not role.is_default()]))

        await ctx.send(embed=em)

    @commands.command(name="avatar", description="Get a users avatar")
    async def avatar(self, ctx, *, user: discord.Member = None):
        if not user:
            user = ctx.author

        async with ctx.typing():
            try:
                color = await self.average_image_color(user.avatar_url_as(format="png"))
            except:
                color = discord.Embed.Empty
        em = discord.Embed(color=color)
        em.set_author(name=user.display_name, icon_url=user.avatar_url)
        em.set_image(url=user.avatar_url)
        await ctx.send(embed=em)

    @commands.command(name="charinfo", description="Get info on a character")
    async def charinfo(self, ctx, *, text):
        if len(text) > 20:
            return await ctx.send(":x: Your text must be shorter than 20 characters")

        info = []
        for character in text:
            digit = f'{ord(character):x}'
            name = unicodedata.name(character, "Name not found")
            info.append(f'`\\U{digit:>08}`: {name} - {character} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>')
        await ctx.send("\n".join(info))

    @commands.command(name="poll", description="Create a poll")
    @commands.guild_only()
    async def poll(self, ctx, title = None, *options):
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

        if not title:
            options = []

            check = lambda message: message.channel == ctx.author.dm_channel and message.author == ctx.author
            try:
                await ctx.author.send("What is the title of the poll?")
            except discord.Forbidden:
                return await ctx.send(":x: You have DMs disabled")

            message = await self.bot.wait_for("message", check=check)
            title = message.content

            await ctx.author.send("Send me up to 10 poll options. Type `done` to send the poll")
            while len(options) < len(possible_reactions):
                message = await self.bot.wait_for("message", check=check)
                if message.content == "done":
                    if len(options) < 2:
                        return await ctx.author.send(":x: You must have at least 2 options")
                    break
                elif message.content == "abort":
                    return await ctx.author.send("Aborting")

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
        if len(options) < 2:
            return await ctx.send(":x: You must have at least 2 options")

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

    @commands.command(name="snowflake", description="Get the timestamp from a Discord snowflake")
    async def snowflake(self, ctx, *, snowflake: int):
        time = discord.utils.snowflake_time(snowflake)
        await ctx.send(time.strftime("%b %d, %Y at %I:%M %p"))

    async def average_image_color(self, icon):
        data = await icon.read()
        image = io.BytesIO(data)

        partial = functools.partial(Image.open, image)
        img = await self.bot.loop.run_in_executor(None, partial)

        partial = functools.partial(img.resize, (1, 1))
        img2 = await self.bot.loop.run_in_executor(None, partial)

        partial = functools.partial(img2.getpixel, (0, 0))
        color = await self.bot.loop.run_in_executor(None, partial)

        return(discord.Color(int("0x{:02x}{:02x}{:02x}".format(*color), 16)))

def setup(bot):
    bot.add_cog(Tools(bot))
