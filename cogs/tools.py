import discord
from discord.ext import commands

import asyncio
import collections
import io
import unicodedata
from typing import Union
from PIL import Image

from .utils import formats, human_time


class Tools(commands.Cog):
    """Various utilities to make your life easier."""

    emoji = "\N{TOOLBOX}"

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Provides information on the current server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        async with ctx.typing():
            color = await self.average_image_color(ctx.guild.icon.with_format("png"))

        static_emojis = len([emoji for emoji in ctx.guild.emojis if not emoji.animated])
        static_emojis_percentage = int(static_emojis / ctx.guild.emoji_limit * 100)
        static_text = f"{static_emojis}/{ctx.guild.emoji_limit} ({static_emojis_percentage}%)"
        animated_emojis = len([emoji for emoji in ctx.guild.emojis if emoji.animated])
        animated_emojis_percentage = int(animated_emojis / ctx.guild.emoji_limit * 100)
        animated_text = f"{animated_emojis} / {ctx.guild.emoji_limit} ({animated_emojis_percentage}%)"
        emoji_percentage = int(len(ctx.guild.emojis) / (ctx.guild.emoji_limit * 2) * 100)
        bot_count = len([member for member in ctx.guild.members if member.bot])

        em = discord.Embed(color=color)
        em.set_author(name=f"{ctx.guild.name} ({ctx.guild.id})", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        em.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        em.add_field(name="<:owner:1341609645214535730> Owner", value=ctx.guild.owner.mention)
        em.add_field(name=":clock3: Created", value=f"{human_time.fulltime(ctx.guild.created_at.replace(tzinfo=None))}")
        em.add_field(name="<:subscriber:808884446739693609> Nitro Boosts", value=f"Tier {ctx.guild.premium_tier} with {len(ctx.guild.premium_subscribers)} boosters")
        em.add_field(name=":family: Members", value=f"{len(ctx.guild.members)} ({formats.plural(bot_count):bot})")
        em.add_field(name=":speech_balloon: Channels", value=f"<:text_channel:822911982319173642> {str(len(ctx.guild.text_channels))} \N{BULLET} <:voice_channel:822912006947733504> {str(len(ctx.guild.voice_channels))}")
        em.add_field(name=":pencil: Emojis", value=f"Static: {static_text} \nAnimated: {animated_text} \nTotal: {len(ctx.guild.emojis)}/{ctx.guild.emoji_limit * 2} ({emoji_percentage}%)")
        em.add_field(name=":bookmark: Roles", value=len(ctx.guild.roles))

        await ctx.send(embed=em)

    @commands.hybrid_command(description="Provides information on a given user", aliases=["ui", "whois"])
    async def userinfo(self, ctx, *, user: Union[discord.Member, discord.User] = commands.Author):
        async with ctx.typing():
            color = await self.average_image_color(user.avatar)

        badges_mapping = {
            discord.UserFlags.staff: "<:staff:808882362820984853>",
            discord.UserFlags.partner: "<:partner:808882401085227059>",
            discord.UserFlags.hypesquad: "<:hypersquad:808882441460252702>",
            discord.UserFlags.bug_hunter: "<:bug_hunter:808882493163962398>",
            discord.UserFlags.hypesquad_bravery: "<:hypesquad_bravery:808882576928407593>",
            discord.UserFlags.hypesquad_brilliance: "<:hypesquad_balance:808882618912735243>",
            discord.UserFlags.hypesquad_balance: "<:hypesquad_balance:808882618912735243>",
            discord.UserFlags.early_supporter: "<:early_supporter:808883560752742430>",
            discord.UserFlags.bug_hunter_level_2: "<:bug_hunter_2:808884426306093076>",
            discord.UserFlags.verified_bot_developer: "<:verified_bot_developer:808884369053581323>",
            discord.UserFlags.discord_certified_moderator: "<:discord_certified_moderator:1341598759456477304>",
            discord.UserFlags.active_developer: "<:active_developer:1341598817471954955>"
        }

        em = discord.Embed(
            description=f"{" ".join([badges_mapping.get(flag, "") for flag in user.public_flags.all()])}",
            color=color
        )
        em.set_author(
            name=f"{user}{f" ({user.display_name})" if user.display_name != user.name else ""}",
            icon_url=user.display_avatar.url
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.set_footer(text=f"{formats.plural(len(user.mutual_guilds)):server} shared | {user.id}")

        lines = []

        if user.bot:
            em.description += " <:bot:1341614747820232765>"
        if user.public_flags.system:
            em.description += " \N{GEAR}\N{VARIATION SELECTOR-16}"

        em.add_field(name=":clock3: Created", value=human_time.fulltime(user.created_at.replace(tzinfo=None)))

        if isinstance(user, discord.Member):
            if user == user.guild.owner:
                em.description += " <:owner:1341609645214535730>"
            if user.premium_since is not None:
                em.add_field(name="<:nitro:808884446739693609> Booster Since", value=human_time.fulltime(user.premium_since))

            em.add_field(name="<:join:922185698587586591> Joined", value=f"{human_time.fulltime(user.joined_at.replace(tzinfo=None))}")

            sorted_members = sorted(user.guild.members, key=lambda x: x.joined_at)
            position = sorted_members.index(user)
            joins = []

            for offset in range(position - 2, position + 3):
                if offset == position:
                    username = str(user)
                    joins.append(f"**{discord.utils.escape_markdown(username)} (#{position+1})**")
                elif 0 <= offset < len(sorted_members):
                    username = str(sorted_members[offset])
                    joins.append(f"{discord.utils.escape_markdown(username)}")

            em.add_field(name="\N{BUSTS IN SILHOUETTE} Join Order", value=" \N{RIGHTWARDS ARROW} ".join(joins), inline=False)

            if len(user.roles) > 1:
                em.add_field(
                    name="Roles",
                    value=" ".join([role.mention for role in reversed(user.roles) if not role.is_default()])
                )

        await ctx.send(embed=em)

    @commands.hybrid_command(description="Shows someone's dowloadable avatar")
    async def avatar(self, ctx, *, user: Union[discord.Member, discord.User] = commands.Author):
        async with ctx.typing():
            color = await self.average_image_color(user.avatar)

        avatar_formats = ["PNG", "JPG", "WEB"]
        if user.display_avatar.is_animated():
            avatar_formats.append("GIF")

        formats_text = [f"[{avatar_formats}]({user.display_avatar.with_format(avatar_format)})" for avatar_format in avatar_formats]

        em = discord.Embed(description=f"View as {formats.join(formats_text, last="or")}", color=color)
        em.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        em.set_image(url=user.display_avatar.with_format("png"))
        await ctx.send(embed=em)

    @commands.hybrid_command(description="Shows information about given characater(s)")
    async def charinfo(self, ctx, *, characters):
        message = ""

        for character in characters:
            digit = f"{ord(character):x}"
            try:
                name = unicodedata.name(character)
            except ValueError:
                message += f"\n`\\U{digit:x:>08}`: {character}"
            else:
                message += f"\n`\\U{digit:>08}`: **{name}** {character}"

        if len(message) > 2000:
            return await ctx.send("\N{CROSS MARK} Information output is too long")

        await ctx.send(message)

    @commands.hybrid_command(description="Converts a Discord snowflake into a timestamp")
    async def snowflake(self, ctx, *, snowflake: int):
        try:
            time = discord.utils.snowflake_time(snowflake)
        except OSError:
            return await ctx.send("\N{CROSS MARK} This an unacceptable snowflake")

        await ctx.send(discord.utils.format_dt(time))

    async def average_image_color(self, icon):
        if icon is None:
            return

        content = await icon.read()
        image = await asyncio.to_thread(Image.open, io.BytesIO(content))
        resized = await asyncio.to_thread(image.resize, (1, 1))
        color = await asyncio.to_thread(resized.getpixel, (0, 0))
        return(discord.Color(int("0x{:02x}{:02x}{:02x}".format(*color), 16)))


async def setup(bot):
    await bot.add_cog(Tools(bot))
