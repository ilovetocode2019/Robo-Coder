import discord
from discord.ext import commands

import argparse
import datetime
import enum
import shlex
import typing
import re
import humanize

from .utils import cache, human_time, menus, formats

class BannedMember(commands.Converter):
    async def convert(self, ctx, arg):
        if arg.isdigit():
            arg = int(arg)
            try:
                return (await ctx.guild.fetch_ban(discord.Object(id=arg))).user
            except discord.NotFound:
                raise commands.BadArgument("That is not a banned user")

        bans = await ctx.guild.bans()
        ban = discord.utils.find(lambda ban: str(ban.user) == arg, bans)
        if not ban:
            raise commands.BadArgument("This is not a banned user")
        return ban.user

class UserID(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            arg = int(arg)
            user = ctx.bot.get_user(arg) or await ctx.bot.fetch_user(arg)
            if not user:
                raise BadArgument()
            return user
        except ValueError:
            raise BadArgument()

class GuildConfig:
    @classmethod
    def from_record(cls, record, bot, cog):
        self = cls()
        self.bot = bot
        self.cog = cog

        self.guild_id = record["guild_id"]
        self.mute_role_id = record["mute_role_id"]
        self.muted = record["muted"]
        self.spam_prevention = record["spam_prevention"]
        self.ignore_spam_channels = record["ignore_spam_channels"]
        self.log_channel_id = record["log_channel_id"]

        return self

    @property
    def guild(self):
        return self.bot.get_guild(self.guild_id)

    @property
    def mute_role(self):
        return self.guild.get_role(self.mute_role_id)

    @property
    def muted_members(self):
        return [self.guild.get_member(member) for member in self.muted]

    @property
    def log_channel(self):
        return self.bot.get_channel(self.log_channel_id)

    async def set_mute_role(self, role):
        self.muted = [member.id for member in role.members]
        self.mute_role_id = role.id if role else None

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET mute_role_id=$2, muted=$3;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def mute_member(self, member):
        self.muted.append(member.id)

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET muted=$3;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def unmute_member(self, member):
        self.muted.remove(member.id)

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET muted=$3;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def enable_spam_prevention(self):
        self.spam_prevention = True

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET spam_prevention=$4;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def disable_spam_prevention(self):
        self.spam_prevention = False

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET spam_prevention=$4;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def add_ignore_spam_channel(self, channel):
        self.ignore_spam_channels.append(channel.id)

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET ignore_spam_channels=$5;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    async def remove_ignore_spam_channel(self, channel):
        self.ignore_spam_channels.remove(channel.id)

        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (guild_id) DO UPDATE
                   SET ignore_spam_channels=$5;
                """
        await self.bot.db.execute(query, self.guild_id, self.mute_role_id, self.muted, self.spam_prevention, self.ignore_spam_channels, self.log_channel_id)
        self.invalidate()

    def invalidate(self):
        self.cog.get_guild_config.invalidate(self.cog, self.guild)

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(add_help=False)

    def error(self, message):
        raise RuntimeError(message)

class CooldownByContent(commands.CooldownMapping):
    def _bucket_key(self, message):
        return (message.channel.id, message.content)

class SpamAction(enum.Enum):
    MUTE = 1
    BAN = 2

class Spammer:
    def __init__(self, member, mute_time, infractions):
        self.members = member
        self.mute_time = mute_time
        self.infractions = infractions

class SpamDetector:
    emoji_regex = re.compile("<:(\w+):(\d+)>")
    url_regex = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""‘’]))")

    def __init__(self, bot):
        self.spammers = {}
        self.bot = bot

        self.by_member = commands.CooldownMapping.from_cooldown(15, 20.0, commands.BucketType.member)
        self.by_content = CooldownByContent.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_mentions = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_links = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_emojis = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_attachments = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)

    def is_spamming(self, message):
        time = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()

        by_member = self.by_member.get_bucket(message)
        if by_member.update_rate_limit(time):
            by_member._window = 0
            return True

        by_content = self.by_content.get_bucket(message)
        if by_content.update_rate_limit(time):
            by_content._window = 0
            return True

        if [mention for mention in message.mentions if not mention.bot and mention.id != message.author.id]:
            by_mentions = self.by_mentions.get_bucket(message)
            if by_mentions.update_rate_limit(time):
                by_mentions._window = 0
                return True

        if self.url_regex.search(message.content):
            by_links = self.by_links.get_bucket(message)
            if by_links.update_rate_limit(time):
                by_links._window = 0
                return True

        if self.emoji_regex.search(message.content) or [emoji for emoji in self.bot.default_emojis if emoji in message.content]:
            by_emojis = self.by_emojis.get_bucket(message)
            if by_emojis.update_rate_limit(time):
                by_emojis._window = 0
                return True

        if message.attachments:
            by_attachments = self.by_attachments.get_bucket(message)
            if by_attachments.update_rate_limit(time):
                by_attachments._window = 0
                return True

        return False

    def get_spammer(self, member):
        spammer = self.spammers.get(member.id)
        if not spammer:
            spammer = Spammer(member, datetime.timedelta(minutes=5), 1)
            self.spammers[member.id] = spammer
            return spammer

        if spammer.mute_time == datetime.timedelta(minutes=5):
            time = datetime.timedelta(minutes=10)
        elif spammer.mute_time == datetime.timedelta(minutes=10):
            time = datetime.timedelta(minutes=30)
        elif spammer.mute_time == datetime.timedelta(minutes=30):
            time = datetime.timedelta(minutes=60)
        elif spammer.mute_time == datetime.timedelta(minutes=60):
            time = datetime.timedelta(minutes=120)
        else:
            time = datetime.timedelta(minutes=360)

        spammer = Spammer(member, time, spammer.infractions+1)
        self.spammers[member.id] = spammer
        return spammer

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_detectors = {}

        self.emoji = ":police_car:"

    @commands.command(name="kick", description="Kick a member from the server")
    @commands.bot_has_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason=None):
        if reason:
            reason = f"Kicked by {ctx.author} with reason {reason}"
        else:
            reason = f"Kicked by {ctx.author}"

        await user.kick(reason=reason)
        await ctx.send(f":white_check_mark: Kicked {user}")

    @commands.command(name="ban", description="Ban a member from the server")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: typing.Union[discord.Member, UserID], *, reason=None):
        if reason:
            reason = f"Banned by {ctx.author} with reason {reason}"
        else:
            reason = f"Banned by {ctx.author}"

        query = """DELETE FROM timers
                   WHERE event = 'tempban'
                   AND extra #>> '{0}' = $1
                   AND extra #>> '{1}' = $2;
                """
        await self.bot.db.execute(query, str(ctx.guild.id), str(user.id))

        if isinstance(user, discord.User):
            await ctx.guild.ban(user, reason=reason)
        elif isinstance(user, discord.Member):
            await user.ban(reason=reason)

        await ctx.send(f":white_check_mark: Banned {user}")

    @commands.command(name="tempban", description="Temporarily ban a member from the server")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def tempban(self, ctx, user: typing.Union[discord.Member, UserID], time: human_time.TimeConverter, *, reason=None):
        if reason:
            reason = f"Tempban by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())} with reason {reason}"
        else:
            reason = f"Tempban by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}"

        query = """DELETE FROM timers
                   WHERE event = 'tempban'
                   AND extra #>> '{0}' = $1
                   AND extra #>> '{1}' = $2;
                """
        await self.bot.db.execute(query, str(ctx.guild.id), str(user.id))

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempban", time, [ctx.guild.id, user.id])

        if isinstance(user, discord.User):
            await ctx.guild.ban(user, reason=reason)
        elif isinstance(user, discord.Member):
            await user.ban(reason=reason)

        await ctx.send(f":white_check_mark: Temporarily banned {user} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.command(name="softban", description="Ban a user and unban them right away")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx, user: typing.Union[discord.Member, UserID], *, reason=None):
        if reason:
            reason = f"Softban by {ctx.author} with reason {reason}"
        else:
            reason = f"Softban by {ctx.author}"

        if isinstance(user, discord.User):
            await ctx.guild.ban(user, reason=reason)
        elif isinstance(user, discord.Member):
            await user.ban(reason=reason)

        await ctx.guild.unban(user, reason=reason)

        await ctx.send(f":white_check_mark: Softbanned {user}")

    @commands.command(name="unban", description="Temporarily ban someone from the server")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: BannedMember, *, reason=None):
        if reason:
            reason = f"Unban by {ctx.author} with reason {reason}"
        else:
            reason = f"Unban by {ctx.author}"

        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f":white_check_mark: Unbanned {user}")

    @commands.group(name="mute", description="Mute a member", invoke_without_command=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_messages=True)
    async def mute(self, ctx, user: discord.Member, *, reason=None):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: Muted role is not set")
        if user.id in config.muted:
            return await ctx.send(":x: This member is already muted")

        if reason:
            reason = f"Mute by {ctx.author} with reason {reason}"
        else:
            reason = f"Mute by {ctx.author}"

        await user.add_roles(config.mute_role)
        await ctx.send(f":white_check_mark: Muted {user}")

    @mute.group(name="role", description="View the current mute role", invoke_without_command=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute_role(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: No mute role has been set")

        await ctx.send(f"The mute role set is {config.mute_role.name} ({config.mute_role_id})")

    @mute_role.command(name="set", description="Set a mute role")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute_role_set(self, ctx, *, role: discord.Role):
        if role.is_default():
            return await ctx.send(":x: Cannot use the default role")
        elif role > ctx.author.top_role:
            return await ctx.send(":x: This role is higher than your highest role")
        elif role > ctx.guild.me.top_role:
            return await ctx.send(":x: This role is higher than my highest role")

        config = await self.get_guild_config(ctx.guild)

        if config.mute_role:
            result = await menus.Confirm("A mute role is already set. Would you like to override it?").prompt(ctx)
            if not result:
                return await ctx.send("Aborting")

        await config.set_mute_role(role)

        await ctx.send(f":white_check_mark: Set mute role to {role.name} ({role.id})")

    @mute_role.command(name="create", description="Create a mute role")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute_role_create(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if config.mute_role:
            result = await menus.Confirm("A mute role is already set. Would you like to override it?").prompt(ctx)
            if not result:
                return await ctx.send("Aborting")

        reason = f"Create mute role by {ctx.author}"
        role = await ctx.guild.create_role(name="Muted", reason=reason)

        channels = ctx.guild.text_channels + ctx.guild.categories
        for channel in channels:
            try:
                overwrite = discord.PermissionOverwrite(send_messages=False, add_reactions=False)
                await channel.set_permissions(role, overwrite=overwrite, reason=reason)
            except discord.HTTPException:
                pass

        await config.set_mute_role(role)
        await ctx.send(f":white_check_mark: Created a mute role and set the overwrites")

    @mute_role.command(name="update", description="Update the mute role", aliases=["sync"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute_role_update(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: No mute role to update")

        reason = f"Update mute role by {ctx.author}"
        channels = ctx.guild.text_channels + ctx.guild.categories

        for channel in channels:
            try:
                overwrite = discord.PermissionOverwrite(send_messages=False, add_reactions=False)
                await channel.set_permissions(config.mute_role, overwrite=overwrite, reason=reason)
            except discord.HTTPException:
                pass

        await ctx.send(":white_check_mark: Successfully updated mute role")

    @mute_role.command(name="unbind", description="Unbind the mute role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute_role_unbind(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: No mute role to unbind")

        result = await menus.Confirm("Are you sure you want to unbind the mute role?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await config.set_mute_role(None)
        await ctx.send(":white_check_mark: Unbound mute role")

    @commands.command(name="unmute", description="Unmute a member")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, user: typing.Union[discord.Member, int], *, reason=None):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: Muted role not set")

        if reason:
            reason = f"Unmute by {ctx.author} with reason {reason}"
        else:
            reason = f"Unmute by {ctx.author}"

        if isinstance(user, int):
            await config.unmute_member(discord.Object(id=user))
            return await ctx.send(f":white_check_mark: Unmuted user with ID of {user}")

        if user.id not in config.muted:
            return await ctx.send(":x: This member is not muted")

        if reason:
            reason = f"Unmute by {ctx.author} with reason {reason}"
        else:
            reason = f"Unmute by {ctx.author}"

        await user.remove_roles(config.mute_role, reason=reason)
        await ctx.send(f":white_check_mark: Unmuted {user}")

    @commands.command(name="muted", description="Mute a member")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def muted(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if len(config.muted_members) == 0:
            return await ctx.send("No muted members")

        muted = [f"[{counter+1}] {str(member)} {f'({member.id})' if isinstance(member, discord.Member) else ''}" for counter, member in enumerate(config.muted_members)]
        muted = "\n".join(muted)
        muted = f"```ini\n{muted}\n```"
        await ctx.send(muted)

    @commands.command(name="tempmute", description="Temporarily mute a member")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def tempmute(self, ctx, user: discord.Member, time: human_time.TimeConverter, *, reason=None):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: Muted role not set")

        if reason:
            reason = f"Tempmute by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())} with reason {reason}"
        else:
            reason = f"Tempmute by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}"

        query = """DELETE FROM timers
                   WHERE event = 'tempmute'
                   AND extra #>> '{0}' = $1
                   AND extra #>> '{1}' = $2;
                """
        await self.bot.db.execute(query, str(ctx.guild.id), str(user.id))

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempmute", time, [ctx.guild.id, user.id])

        await user.add_roles(config.mute_role, reason=reason)
        await ctx.send(f":white_check_mark: Temporarily muted {user} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.command(name="selfmute", description="Mute yourself")
    @commands.bot_has_permissions(manage_roles=True)
    async def selfmute(self, ctx, time: human_time.TimeConverter, *, reason=None):
        config = await self.get_guild_config(ctx.guild)

        delta = time-datetime.datetime.utcnow()
        if delta > datetime.timedelta(days=1):
            return await ctx.send(":x: You cannot mute yourself for more than a day")
        if delta+datetime.timedelta(seconds=1) <= datetime.timedelta(minutes=5):
            return await ctx.send(":x: You must mute yourself for at least 5 minutes")

        if not config.mute_role:
            return await ctx.send(":x: Muted role not set")
        if ctx.author.id in config.muted:
            return await ctx.send(":x: You are already muted")

        if reason:
            reason = f"Selfmute by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())} with reason {reason}"
        else:
            reason = f"Selfmute by {ctx.author} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}"

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempmute", time, [ctx.guild.id, ctx.author.id])

        result = await menus.Confirm("Are you sure you want to mute yourself?").prompt(ctx)
        if not result:
            return await ctx.send("Aborting")

        await ctx.author.add_roles(config.mute_role, reason=reason)
        await ctx.send(f":white_check_mark: You have been muted for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.group(name="spam", description="View the current spam prevention settings", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def spam(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if config.spam_prevention:
            await ctx.send(f"Spam prevention is enabled")
        else:
            await ctx.send(f"Spam prevention is disabled")

    @spam.command(name="enable", description="Enable spam prevention", aliases=["on"])
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def spam_enable(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: There must be a mute role set for spam prevention")

        await config.enable_spam_prevention()
        await ctx.send(":white_check_mark: Spam prevention now enabled")

    @spam.command(name="disable", description="Disable spam prevention", aliases=["off"])
    @commands.has_permissions(manage_guild=True)
    async def spam_disable(self, ctx):
        config = await self.get_guild_config(ctx.guild)
        await config.disable_spam_prevention()
        await ctx.send(":white_check_mark: Spam prevention is now disabled")

    @spam.command(name="ignore", description="Add a channel to the ignore list for spam detection")
    @commands.has_permissions(manage_guild=True)
    async def spam_ignore(self, ctx, *, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel

        config = await self.get_guild_config(ctx.guild)
        if channel.id in config.ignore_spam_channels:
            return await ctx.send(":x: Channel is already being ignored")

        await config.add_ignore_spam_channel(channel)
        await ctx.send(f":white_check_mark: Spam prevention is disabled for {channel.mention}")

    @spam.command(name="unignore", description="Remove a channel from the ignore list for spam detection")
    @commands.has_permissions(manage_guild=True)
    async def spam_unignore(self, ctx, *, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel

        config = await self.get_guild_config(ctx.guild)
        if channel.id not in config.ignore_spam_channels:
            return await ctx.send(":x: Channel is not ignored")

        await config.remove_ignore_spam_channel(channel)
        await ctx.send(f":white_check_mark: Spam prevention is disabled for {channel.mention}")

    @spam.command(name="reset", description="Reset a member's automatic mute time")
    @commands.has_permissions(manage_guild=True)
    async def spam_reset(self, ctx, *, user: discord.Member):
        detector = self.spam_detectors[ctx.guild.id]
        if user.id not in detector.spammers:
            return await ctx.send(":x: This user isn't a spammer")

        detector.spammers.pop(user.id)
        await ctx.send(f":white_check_mark: Reset automatic mute time for {user}")

    @commands.command(name="purge", description="Purge messages from a channel", usage="[limit=100]")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, limit: typing.Optional[int] = 100, *, flags = None):
        if flags:
            parser = ArgumentParser()

            parser.add_argument("--or", action="store_true", dest="_or")
            parser.add_argument("--not", action="store_true", dest="_not")

            parser.add_argument("--user", nargs="+")
            parser.add_argument("--contains", nargs="+")
            parser.add_argument("--starts", nargs="+")
            parser.add_argument("--ends", nargs="+")

            parser.add_argument("--emoji", action="store_true")
            parser.add_argument("--bot", action="store_true")
            parser.add_argument("--embeds", action="store_true")
            parser.add_argument("--files", action="store_true")
            parser.add_argument("--reactions", action="store_true")
            parser.add_argument("--after", type=int)
            parser.add_argument("--before", type=int)

            try:
                args = parser.parse_args(shlex.split(flags))
            except Exception as e:
                return await ctx.send(str(e))

            checks = []
            if args.user:
                users = []
                converter = commands.MemberConverter()
                for arg in args.user:
                    try:
                        user = await converter.convert(ctx, arg)
                        users.append(user)
                    except commands.BadArgument as exc:
                        return await ctx.send(f":x: {exc}")
                checks.append(lambda message: message.author in users)

            if args.contains:
                checks.append(lambda message: any(sub in message.content for sub in args.contains))
            if args.starts:
                checks.append(lambda message: any(message.startswith(start) for start in args.starts))
            if args.ends:
                checks.append(lambda message: any(message.endswith(end) for end in args.ends))

            if args.emoji:
                regex = re.compile("<:(\w+):(\d+)>")
                checks.append(lambda message: regex.search(message.content))
            if args.bot:
                checks.append(lambda message: message.author.bot)
            if args.embeds:
                checks.append(lambda message: len(message.embeds) != 0)
            if args.files:
                chekcs.append(lambda message: len(message.attachments) != 0)
            if args.reactions:
                checks.append(lambda message: len(message.reactions) != 0)

            if args.before:
                before = discord.Object(id=args.before)
            else:
                before = ctx.message

            if args.after:
                after = discord.Object(id=args.after)
            else:
                after = None

            def check(message):
                results = [check(message) for check in checks]
                result = any(results) if args._or else all(results)
                if args._not:
                    return not result
                else:
                    return result

        if flags:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=check)
        else:
            deleted = await ctx.channel.purge(limit=limit, before=ctx.message)

        await ctx.message.delete()
        await ctx.send(f":white_check_mark: Deleted {formats.plural(len(deleted)):messages}", delete_after=5)

    @commands.command(name="cleanup", description="Clean up commands from a channel")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def cleanup(self, ctx, limit=100):
        if ctx.guild.me.guild_permissions.manage_messages:
            method = self.complex_cleanup
        else:
            method = self.basic_cleanup

        deleted = await method(ctx, limit+1)
        await ctx.send(f":white_check_mark: Deleted {formats.plural(len(deleted)):messages}", delete_after=5)

    async def basic_cleanup(self, ctx, limit):
        deleted = []
        async for message in ctx.history(limit=limit):
            if message.author.id == self.bot.user.id:
                await message.delete()
                deleted.append(message)
        return deleted

    async def complex_cleanup(self, ctx, limit):
        prefixes = self.bot.guild_prefixes[str(ctx.guild.id)]
        prefixes.append(self.bot.user.mention)
        deleted = await ctx.channel.purge(limit=limit, check=lambda message: message.author.id == self.bot.user.id or message.content.startswith(tuple(prefixes)))
        return deleted

    @cache.cache()
    async def get_guild_config(self, guild):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        record = await self.bot.db.fetchrow(query, guild.id)

        if not record:
            record =  {
                "guild_id": guild.id,
                "mute_role_id": None,
                "muted": [],
                "spam_prevention": False,
                "ignore_spam_channels": [],
                "log_channel_id": None
            }

        return GuildConfig.from_record(dict(record), self.bot, self)

    def get_spam_action(self, config, spammer):
        return SpamAction.MUTE

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return

        config = await self.get_guild_config(message.guild)

        if not config.spam_prevention:
            return
        if message.channel.id in config.ignore_spam_channels:
            return

        if message.guild.id in self.spam_detectors:
            detector = self.spam_detectors[message.guild.id]
        else:
            detector = SpamDetector(self.bot)
            self.spam_detectors[message.guild.id] = detector

        if detector.is_spamming(message):
            spammer = detector.get_spammer(message.author)
            action = self.get_spam_action(config, spammer)

            if action == SpamAction.MUTE:
                timers = self.bot.get_cog("Timers")
                if timers:
                    await timers.create_timer("tempmute", datetime.datetime.utcnow()+spammer.mute_time, [message.guild.id, message.author.id])
                    await message.author.add_roles(config.mute_role, reason=f"Automatic mute for spamming ({humanize.naturaldelta(spammer.mute_time)})")
            else:
                await message.author.ban(reason=f"Automatic ban for spamming")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        config = await self.get_guild_config(after.guild)
        if not config.mute_role:
            return

        if config.mute_role_id in [role.id for role in after.roles] and after.id not in config.muted:
            await config.mute_member(after)

        elif config.mute_role_id not in [role.id for role in after.roles] and after.id in config.muted:
            query = """DELETE FROM timers
                       WHERE event = 'tempmute'
                       AND extra #>> '{0}' = $1
                       AND extra #>> '{1}' = $2;
                    """
            await self.bot.db.execute(query, str(after.guild.id), str(after.id))
            await config.unmute_member(after)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        query = """DELETE FROM timers
                   WHERE event = 'tempban'
                   AND extra #>> '{0}' = $1
                   AND extra #>> '{1}' = $2;
                """
        await self.bot.db.execute(query, str(guild.id), str(user.id))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_guild_config(member.guild)

        if member.id in config.muted and config.mute_role:
            await member.add_roles(config.mute_role, reason=f"User was muted when they left")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        config = await self.get_guild_config(role.guild)

        if role.id == config.mute_role_id:
            await config.set_mute_role(None)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        config = await self.get_guild_config(channel.guild)

        if channel.id in config.ignore_spam_channels:
            await config.remove_ignore_spam_channel(channel)

    @commands.Cog.listener()
    async def on_tempban_complete(self, timer):
        guild = self.bot.get_guild(timer["extra"][0])
        user = discord.Object(id=timer["extra"][1])

        await guild.unban(user, reason="Tempban is over")

    @commands.Cog.listener()
    async def on_tempmute_complete(self, timer):
        guild = self.bot.get_guild(timer["extra"][0])
        user = guild.get_member(timer["extra"][1])

        config = await self.get_guild_config(guild)

        if user:
            await user.remove_roles(config.mute_role, reason=f"Tempmute is over")

        else:
            await config.unmute_member(discord.Object(id=timer["extra"][1]))

def setup(bot):
    bot.add_cog(Moderation(bot))
