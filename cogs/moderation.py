import discord
from discord.ext import commands

import datetime
import humanize
import typing
import collections
import enum
import dateparser
import asyncio
import functools
import inspect

class LRUDict(collections.OrderedDict):
    def __init__(self, max_legnth = 10, *args, **kwargs):
        if max_legnth <= 0:
            raise ValueError()
        self.max_legnth = max_legnth

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)

        if len(self) > 10:
            super().__delitem__(list(self)[0])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

def cache(max_legnth = 100):
    def decorator(func):
        cache = LRUDict(max_legnth=max_legnth)

        def __len__():
            return len(cache)

        def _get_key(*args, **kwargs):
            return f"{':'.join([repr(arg) for arg in args])}{':'.join([f'{repr(kwarg)}:{repr(value)}' for kwarg, value in kwargs.items()])}"

        def invalidate(*args, **kwargs):
            if not args:
                cache.clear()
                return

            try:
                key = _get_key(*args)
                del cache[key]
                return True
            except KeyError:
                return False

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            key = _get_key(*args, **kwargs)

            try:
                value = cache[key]
                if asyncio.iscoroutinefunction(func):
                    async def coro():
                        return value
                    return coro()
                return value

            except KeyError:
                value = func(*args, **kwargs)
                if inspect.isawaitable(value):
                    async def coro():
                        result = await value
                        cache[key] = result
                        return result
                    return coro()

                cache[key] = value
                return value


        wrapped.invalidate = invalidate
        wrapped.cache = cache
        wrapped._get_key = _get_key
        wrapped.__len__ = __len__
        return wrapped

    return decorator

class TimeConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            if not arg.startswith("in") and not arg.startswith("at"):
                arg = f"in {arg}"
            time = dateparser.parse(arg, settings={"TIMEZONE": "UTC"})
        except:
            raise commands.BadArgument("Failed to parse time")
        if not time:
            raise commands.BadArgument("Failed to parse time")
        return time

class BannedMember(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            arg = int(arg)
            return (await ctx.guild.fetch_ban(discord.Object(id=arg))).user
        except ValueError:
            raise commands.BadArgument(f"You must provide an ID")
        except discord.NotFound:
            raise commands.BadArgument(f"That is not a banned member")

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
        self.muted = []
        self.mute_role_id = role.id
        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, self.mute_role_id, self.muted, self.guild_id)
        self.invalidate()

    async def mute_member(self, member):
        self.muted.append(member.id)
        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.muted, self.guild_id)
        self.invalidate()

    async def unmute_member(self, member):
        self.muted.remove(member.id)
        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.muted, self.guild_id)
        self.invalidate()

    async def enable_spam_prevention(self):
        query = """UPDATE guild_config
                   SET spam_prevention=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, True, self.guild_id)
        self.invalidate()

    async def disable_spam_prevention(self):
        query = """UPDATE guild_config
                   SET spam_prevention=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, False, self.guild_id)
        self.invalidate()

    async def add_ignore_spam_channel(self, channel):
        self.ignore_spam_channels.append(channel.id)
        query = """UPDATE guild_config
                   SET ignore_spam_channels=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.ignore_spam_channels, self.guild_id)
        self.invalidate()

    async def remove_ignore_spam_channel(self, channel):
        self.ignore_spam_channels.remove(channel.id)
        query = """UPDATE guild_config
                   SET ignore_spam_channels=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.ignore_spam_channels, self.guild_id)
        self.invalidate()

    def invalidate(self):
        self.cog.get_guild_config.invalidate(self.cog, self.guild)

class CooldownByContent(commands.CooldownMapping):
    def _bucket_key(self, message):
        return (message.channel.id, message.content)

class Spammer:
    def __init__(self, mute_time):
        self.mute_time = mute_time

class SpamDetector:
    def __init__(self):
        self.spammers = {}
        self.by_content = CooldownByContent.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_attachment = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_mention = commands.CooldownMapping.from_cooldown(10, 30.0, commands.BucketType.member)
        self.by_member = commands.CooldownMapping.from_cooldown(15, 20.0, commands.BucketType.member)

    def is_spamming(self, message):
        time = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()

        by_content = self.by_content.get_bucket(message)
        if by_content.update_rate_limit(time):
            return True

        if message.attachments:
            by_attachment = self.by_attachment.get_bucket(message)
            if by_attachment.update_rate_limit(time):
                return True

        if [mention for mention in message.mentions if not mention.bot and mention.id != message.author.id]:
            by_mention = self.by_mention.get_bucket(message)
            if by_mention.update_rate_limit(time):
                return True

        by_member = self.by_member.get_bucket(message)
        if by_member.update_rate_limit(time):
            return True

        return False

    def get_mute_time(self, member):
        spammer = self.spammers.get(member.id)
        if not spammer:
            self.spammers[member.id] = Spammer(datetime.timedelta(minutes=5))
            return datetime.timedelta(minutes=5) 

        if spammer.mute_time == datetime.timedelta(minutes=5):
            time = datetime.timedelta(minutes=10)
        elif spammer.mute_time == datetime.timedelta(minutes=10):
            time = datetime.timedelta(minutes=30)
        elif spammer.mute_time == datetime.timedelta(minutes=30):
            time = datetime.timedelta(minutes=60)
        elif spammer.mute_time == datetime.timedelta(minutes=60):
            time = datetime.timedelta(minutes=120)
        elif spammer.mute_time == datetime.timedelta(minutes=120):
            time = datetime.timedelta(minutes=360)

        self.spammers[member.id] = Spammer(time)
        return time

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_detectors = collections.defaultdict(SpamDetector)

        self.emoji = ":police_car:"

    @cache()
    async def get_guild_config(self, guild, create_if_not_exists=True):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        record = await self.bot.db.fetchrow(query, guild.id)
        if not record:
            if create_if_not_exists:
                record = await self.create_guild_config(guild)
            else:
                return

        return GuildConfig.from_record(record, self.bot, self)

    async def create_guild_config(self, guild):
        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted, spam_prevention, ignore_spam_channels, log_channel_id)
                   VALUES ($1, $2, $3, $4, $5, $6);
                """
        await self.bot.db.execute(query, guild.id, None, [], False, [], None)

        return {
            "guild_id": guild.id,
            "mute_role_id": None,
            "muted": [],
            "spam_prevention": False,
            "ignore_spam_channels": [],
            "log_channel_id": None
        }

    @commands.command(name="purge", description="Purge messages from a channel")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, limit=100):
        purged = await ctx.channel.purge(limit=limit+1)
        await ctx.send(f":white_check_mark: Deleted {len(purged)} message(s)", delete_after=5)

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
    async def ban(self, ctx, user: discord.Member, *, reason=None):
        if reason:
            reason = f"Banned by {ctx.author} with reason {reason}"
        else:
            reason = f"Banned by {ctx.author}"

        await user.ban(reason=reason)
        await ctx.send(f":white_check_mark: Banned {user}")

    @commands.command(name="tempban", description="Temporarily ban a member from the server")
    @commands.bot_has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def tempban(self, ctx, user: discord.Member, time: TimeConverter, *, reason=None):
        if reason:
            reason = f"Temporarily banned by {ctx.author} with reason {reason}"
        else:
            reason = f"Temporarily banned by {ctx.author}"

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempban", time, [ctx.guild.id, user.id])

        await user.ban(reason=reason)
        await ctx.send(f":white_check_mark: Temporarily banned {user} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

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
        config = await self.get_guild_config(ctx.guild)
        await config.set_mute_role(role)

        await ctx.send(f":white_check_mark: Set mute role to {role.name} ({role.id})")

    @mute_role.command(name="create", description="Create a mute role")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def mute_role_create(self, ctx):
        config = await self.get_guild_config(ctx.guild)
        reason = f"Creation of mute role by {ctx.author}"
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
            return await ctx.send(":x: No muted members")

        muted = [f"[{counter+1}] {str(member)} {f'({member.id})' if isinstance(member, discord.Member) else ''}" for counter, member in enumerate(config.muted_members)]
        muted = "\n".join(muted)
        muted = f"```ini\n{muted}\n```"
        await ctx.send(muted)

    @commands.command(name="tempmute", description="Temporarily mute a member")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    async def tempmute(self, ctx, user: discord.Member, time: TimeConverter, *, reason=None):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: Muted role not set")

        if reason:
            reason = f"Tempmute by {ctx.author} with reason {reason}"
        else:
            reason = f"Tempmute by {ctx.author}"

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempmute", time, [ctx.guild.id, user.id])

        await user.add_roles(config.mute_role, reason=reason)
        await ctx.send(f":white_check_mark: Temporarily muted {user} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.command(name="selfmute", description="Mute yourself")
    @commands.bot_has_permissions(manage_roles=True)
    async def selfmute(self, ctx, time: TimeConverter, *, reason=None):
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
            reason = f"Selfmute by {ctx.author} with reason {reason}"
        else:
            reason = f"Selfmute by {ctx.author}"

        timers = self.bot.get_cog("Timers")
        if not timers:
            return await ctx.send(":x: This feature is temporarily unavailable")
        await timers.create_timer("tempmute", time, [ctx.guild.id, ctx.author.id])

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

    @spam.command(name="enable", description="Enable spam prevention")
    @commands.has_permissions(manage_guild=True)
    async def spam_enable(self, ctx):
        config = await self.get_guild_config(ctx.guild)

        if not config.mute_role:
            return await ctx.send(":x: There must be a mute role set for spam prevention")

        await config.enable_spam_prevention()
        await ctx.send(":white_check_mark: Spam prevention now enabled")

    @spam.command(name="disable", description="Disable spam prevention")
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return

        config = await self.get_guild_config(message.guild, create_if_not_exists=False)

        if not config or not config.spam_prevention:
            return
        if message.channel.id in config.ignore_spam_channels:
            return

        detector = self.spam_detectors[message.guild.id]
        if detector.is_spamming(message):
            timers = self.bot.get_cog("Timers")
            if timers:
                mute_time = detector.get_mute_time(message.author)
                await timers.create_timer("tempmute", datetime.datetime.utcnow()+mute_time, [message.guild.id, message.author.id])
                await message.author.add_roles(config.mute_role, reason=f"Automatic mute for spamming ({humanize.naturaldelta(mute_time)})")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        config = await self.get_guild_config(after.guild, create_if_not_exists=False)
        if not config:
            return

        if config.mute_role_id in [role.id for role in after.roles] and after.id not in config.muted:
            await config.mute_member(after)
        elif config.mute_role_id not in [role.id for role in after.roles] and after.id in config.muted:
            await config.unmute_member(after)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_guild_config(member.guild, create_if_not_exists=False)
        if not config:
            return

        if member.id in config.muted and config.mute_role:
            await member.add_roles(config.mute_role, reason=f"User was muted when they left")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        config = await self.get_guild_config(role.guild, create_if_not_exists=False)
        if not config:
            return

        if role.id == config.mute_role.id:
            await config.set_mute_role(None)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        config = await self.get_guild_config(channel.guild, create_if_not_exists=False)
        if not config:
            return

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
