import discord
from discord.ext import commands

import datetime
import humanize
import typing

import dateparser

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
    def from_record(cls, record, bot):
        self = cls()
        self.bot = bot

        self.guild_id = record["guild_id"]
        self.mute_role_id = record["mute_role_id"]
        self.muted = record["muted"]

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

    async def set_mute_role(self, role):
        self.muted = []
        self.mute_role_id = role.id

        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, self.mute_role_id, self.muted, self.guild_id)

    async def mute_member(self, member):
        self.muted.append(member.id)

        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.muted, self.guild_id)

    async def unmute_member(self, member):
        self.muted.remove(member.id)

        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, self.muted, self.guild_id)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":police_car:"

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

        return GuildConfig.from_record(record, self.bot)

    async def create_guild_config(self, guild):
        query = """INSERT INTO guild_config (guild_id, mute_role_id, muted)
                   VALUES ($1, $2, $3);
                """
        await self.bot.db.execute(query, guild.id, None, [])

        return {
            "guild_id": guild.id,
            "mute_role_id": None,
            "muted": []
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
