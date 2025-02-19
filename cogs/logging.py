import discord
from discord.ext import commands

from .utils import cache


class MessageLog:
    __slots__ = ("cog", "guild_id", "channel_id")

    @classmethod
    def from_record(cls, record, cog):
        self = cls()
        self.cog = cog
        self.guild_id = record["guild_id"]
        self.channel_id = record["channel_id"]
        return self

    @property
    def guild(self):
        return self.cog.bot.get_guild(self.guild_id)

    @property
    def channel(self):
        if self.channel_id is not None:
            return self.guild.get_channel(self.channel_id)

    async def set_channel(self, channel_id):
        self.channel_id = channel_id

        query = """INSERT INTO message_logs (guild_id, channel_id)
                   VALUES ($1, $2)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET channel_id=$2;
                """
        await self.cog.bot.db.execute(query, self.guild_id, self.channel_id)


class EditedView(discord.ui.View):
    def __init__(self, message):
        super().__init__()
        jump_button = discord.ui.Button(url=message.jump_url, label="Go To Message", style=discord.ButtonStyle.secondary)
        self.add_item(jump_button)


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":notepad_spiral:"

    def cog_check(self, ctx):
        return ctx.guild is not None and ctx.guild.id in self.bot.config.logging_guild_ids

    @cache.cache()
    async def get_message_log(self, guild_id):
        query = """SELECT *
                   FROM message_logs
                   WHERE message_logs.guild_id=$1;
                """

        record = await self.bot.db.fetchrow(query, guild_id)

        if record is None:
            record =  {"guild_id": guild_id, "channel_id": None}

        return MessageLog.from_record(dict(record), self)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.guild.id not in self.bot.config.logging_guild_ids:
            return
        elif message.author.bot:
            return

        log = await self.get_message_log(message.guild.id)

        if log.channel is None:
            return

        em = discord.Embed(title="Message Deleted", color=0xff4545, timestamp=message.created_at)
        em.set_author(name=f"{message.author.display_name} ({message.author.id})", icon_url=message.author.display_avatar.url)
        em.set_footer(text="Sent")
        em.add_field(name="Content", value=f"{message.content[:1000]}{'...' if len(message.content) > 1000 else ''}", inline=False)
        em.add_field(name="Channel", value=message.channel.mention, inline=False)
        await log.channel.send(embed=em)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild is None or after.guild.id not in self.bot.config.logging_guild_ids:
            return
        elif after.author.bot:
            return

        log = await self.get_message_log(after.guild.id)

        if log.channel is None:
            return

        em = discord.Embed(title="Message Edited", color=0xeed202)
        em.set_author(name=f"{after.author.display_name} ({after.author.id})", icon_url=after.author.display_avatar.url)
        em.add_field(name="Before", value=f"{before.content[:1000]}{'...' if len(before.content) > 1000 else ''}")
        em.add_field(name="After", value=f"{after.content[:1000]}{'...' if len(after.content) > 1000 else ''}")
        await log.channel.send(embed=em, view=EditedView(after))

    @commands.hybrid_group(invoke_without_command=True, fallback="show", description="Shows the current message logging channel")
    async def log(self, ctx):
        log = await self.get_message_log(ctx.guild.id)

        if log.channel is not None:
            await ctx.send(f"Message logging is set to {log.channel.mention}")
        else:
            await ctx.send("Message logging is not enabled")

    @log.command(name="set", description="Sets a channel for messages to be logged to")
    async def log_set(self, ctx, channel: discord.TextChannel):
        log = await self.get_message_log(ctx.guild.id)
        await log.set_channel(channel.id)
        await ctx.send(f"Message logging set to {channel.mention}")

    @log.command(name="disable", description="Disables logging of messages")
    async def log_disable(self, ctx):
        log = await self.get_message_log(ctx.guild.id)
        await log.set_channel(None)
        await ctx.send(f"Message logging disabled")


async def setup(bot):
    await bot.add_cog(
        Logging(bot),
        guilds=[discord.Object(id=guild_id) for guild_id in bot.config.logging_guild_ids]
    )
