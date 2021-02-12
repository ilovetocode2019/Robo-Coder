import discord
from discord.ext import commands

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

from .utils import human_time, formats

class AnyUser(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            return await commands.MemberConverter().convert(ctx, arg)
        except commands.BadArgument:
            pass

        try:
            return await commands.UserConverter().convert(ctx, arg)
        except commands.BadArgument:
            pass

        try:
            return await ctx.bot.fetch_user(arg)
        except:
            raise commands.BadArgument(f"User `{arg}` not found")

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
        em.add_field(name=":clock1: Created", value=f"{human_time.fulltime(guild.created_at)}")
        em.add_field(name="<:nitro:808884446739693609> Nitro Boosts", value=guild.premium_tier)
        bots = len([member for member in guild.members if member.bot])
        em.add_field(name=":earth_americas: Region", value=str(guild.region).upper().replace("-", " "))
        em.add_field(name=":family: Members", value=f"{len(guild.members)} ({formats.plural(bots):bot})")
        em.add_field(name=":speech_balloon: Channels", value=f"<:textchannel:725730867644858518> {str(len(guild.text_channels))} \N{BULLET} <:voicechannel:725730883872751666> {str(len(guild.voice_channels))}")

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
    async def userinfo(self, ctx, *, user: AnyUser = None):
        if not user:
            user = ctx.author
        is_member = isinstance(user, discord.Member)

        pubilic_flags_mapping = {
            discord.UserFlags.staff: "<:staff:808882362820984853>",
            discord.UserFlags.partner: "<:partner:808882401085227059>",
            discord.UserFlags.hypesquad: "<:hypersquad:808882441460252702>",
            discord.UserFlags.bug_hunter: "<:bug_hunter:808882493163962398>",
            discord.UserFlags.bug_hunter_level_2: "<:bug_hunter_2:808884426306093076>",
            discord.UserFlags.hypesquad_bravery: "<:hypesquad_bravery:808882576928407593>",
            discord.UserFlags.hypesquad_brilliance: "<:hypesquad_balance:808882618912735243>",
            discord.UserFlags.hypesquad_balance: "<:hypesquad_balance:808882618912735243>",
            discord.UserFlags.early_supporter: "<:early_supporter:808883560752742430>",
            discord.UserFlags.verified_bot_developer: "<:verified_bot_developer:808884369053581323>",
        }

        badges = ""
        for flag in user.public_flags.all():
            emoji = pubilic_flags_mapping.get(flag)
            if emoji:
                badges += emoji

        async with ctx.typing():
            if is_member and not ctx.guild.chunked:
                await ctx.guild.chunk(cache=True)

            try:
                color = await self.average_image_color(user.avatar_url_as(format="png"))
            except:
                color = user.color

        if is_member:
            name = f"{user}{f' ({user.nick})' if user.nick else ''} - {user.id}"
        else:
            name = f"{user} - {user.id}"

        em = discord.Embed(description=badges, color=color)
        em.set_author(name=name, icon_url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n:crown: This user owns the server"
        if user.bot:
            em.description += "\n:robot: This user is a bot"
        if user.id == self.bot.user.id:
            em.description +="\n:wave: This user is me"
        if is_member and user.premium_since:
            em.description += f"\n<:nitro:808884446739693609> This user has been bosting since {human_time.fulltime(user.joined_at)}"

        if user.public_flags.team_user:
            em.description += "\n:family: This user is a team user"
        if user.public_flags.system:
            em.description += "\n:gear: This user is a system user"
        if user.public_flags.verified_bot:
            em.description += "\n:white_check_mark: This user is a verified bot"

        em.add_field(name=":clock3: Created", value=human_time.fulltime(user.created_at))

        if is_member:
            em.add_field(name=":arrow_right: Joined", value=f"{human_time.fulltime(user.joined_at)}")

            sorted_members = sorted(ctx.guild.members, key=lambda x: x.joined_at)
            for position, member in enumerate(sorted_members):
                if member == user:
                    break

            joins = []
            if position > 1:
                joins.append(f"{sorted_members[position-2]}")
            if position > 0:
                joins.append(f"{sorted_members[position-1]}")

            joins.append(f"**{user} (#{position+1})**")

            if position < len(sorted_members) - 1:
                joins.append(f"{sorted_members[position+1]})")
            if position < len(sorted_members) - 2:
                joins.append(f"{sorted_members[position+2]}")

            em.add_field(name=":busts_in_silhouette: Join Order", value=" → ".join(joins), inline=False)

            if len(user.roles) > 1:
                em.add_field(name="Roles", value=" ".join([role.mention for role in reversed(user.roles) if not role.is_default()]))

        shared = [guild for guild in self.bot.guilds if discord.utils.get(guild.members, id=user.id)]
        if shared:
            em.set_footer(text=f"{formats.plural(len(shared)):server} shared")

        await ctx.send(embed=em)

    @commands.command(name="avatar", description="View someone's avatar", usage="[user] [--format FORMAT]")
    async def avatar(self, ctx, *, user = ""):    
        if user in ("--format png", "--format jpg", "--format jpeg", "--format webp"):
            if user.endswith(("png", "jpg")):
                view_format = user[-3:]
                user = ""
            elif user.endswith(("jpeg", "webp")):
                view_format = user[-4:]
                user = ""
        elif user.endswith((" --format png", " --format jpg", " --format jpeg", " --format webp")):
            if user.endswith(("png", "jpg")):
                view_format = user[-3:]
                user = user[:len(user)-13]
            elif user.endswith(("jpeg", "webp")):
                view_format = user[-4:]
                user = user[:len(user)-14]

        else:
            view_format = "png"

        if user:
            user = await commands.MemberConverter().convert(ctx, user)
        else:
            user = ctx.author

        async with ctx.typing():
            try:
                color = await self.average_image_color(user.avatar_url_as(format="png"))
            except:
                color = discord.Embed.Empty

        avatar_formats = ["png", "jpg", "webp"]
        if user.is_avatar_animated():
            avatar_formats.append("gif")

        formats_text = [f"[{avatar_format.upper()}]({user.avatar_url_as(format=avatar_format)})" for avatar_format in avatar_formats]

        em = discord.Embed(description=f"View as {formats.join(formats_text, last='or')}", color=color)
        em.set_author(name=user.display_name, icon_url=user.avatar_url)
        em.set_image(url=user.avatar_url_as(static_format=view_format))
        await ctx.send(embed=em)

    @commands.command(name="charinfo", description="Get info on a character")
    async def charinfo(self, ctx, *, text):
        if len(text) > 20:
            return await ctx.send(":x: Your text must be shorter than 20 characters")

        info = []
        for character in text:
            digit = f"{ord(character):x}"
            name = unicodedata.name(character, "Name not found")
            info.append(f"`\\U{digit:>08}`: {name} - {character} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>")
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

    @commands.command(name="snowstamp", description="Get the timestamp from a Discord snowflake", hidden=True)
    async def snowflake(self, ctx, *, snowflake: int):
        time = discord.utils.snowflake_time(snowflake)
        await ctx.send(human_time.format_time(time))

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
