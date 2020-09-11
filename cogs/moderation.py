import discord
from discord.ext import commands

import typing
import dateparser
import humanize
import datetime

class TimeConverter(commands.Converter):
    """Converts a string to datetime.datetime."""

    async def convert(self, ctx, arg):
        try:
            if not arg.startswith("in") and not arg.startswith("at"):
                time = f"in {arg}"
            else:
                time = arg

            time = dateparser.parse(time, settings={"TIMEZONE": "UTC"})
        except:
            time = None

        if not time:
            raise commands.BadArgument("Could not parse your time")
        return time

class BannedUser(commands.Converter):
    """Converts a string to a banned user."""

    async def convert(self, ctx, arg):
        try:
            arg = int(arg)
            user = discord.Object(id=arg)
        except ValueError:
            user = None

        if not user:
            raise commands.BadArgument("User is not banned")
        return user

class Moderation(commands.Cog):
    """Moderation commands for Discord servers."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":police_car:"

    async def cog_before_invoke(self, ctx):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        ctx.guild_config = await self.bot.db.fetchrow(query, ctx.guild.id)

        if not ctx.guild_config:
            query = """INSERT INTO guild_config (guild_id, mute_role_id, muted)
                       VALUES ($1, $2, $3);
                    """
            await self.bot.db.execute(query, ctx.guild.id, None, [])
            ctx.guild_config = {"guild_id": ctx.guild.id, "mute_role_id": None, "muted": []}

    @commands.command(name="kick", description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason=None):
        if reason:
            reason = f"Kick by {ctx.author} with reason {reason}"
        await user.kick(reason=reason or f"Kick by {ctx.author}")
        await ctx.send(f":white_check_mark: Kicked {user.display_name}")

    @commands.command(name="ban", description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, *, reason=None):
        if reason:
            reason = f"Ban by {ctx.author} with reason {reason}"
        await user.ban(reason=reason or f"Ban by {ctx.author}")
        await ctx.send(f":white_check_mark: Banned {user.display_name}")

    @commands.command(name="tempban", description="Temporarily ban a member from the server")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def tempban(self, ctx, user: discord.Member, time: TimeConverter, *, reason=None):
        if reason:
            reason = f"Temporary ban by {ctx.author} with reason {reason}"

        query = """INSERT INTO tasks (task, guild_id, channel_id, user_id, time)
                   VALUES ($1, $2, $3, $4, $5);
                """
        await self.bot.db.execute(query, "unban", ctx.guild.id, ctx.channel.id, user.id, time)

        await user.ban(reason=reason or f"Temporary ban by {ctx.author}")
        await ctx.send(f":white_check_mark: Temporarily banned {user.display_name} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.command(name="unban", description="Unban a user")
    @commands.has_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: BannedUser, *, reason=None):
        if reason:
            reason = f"Unban by {ctx.author} with reason {reason}"

        try:
            await ctx.guild.unban(user, reason=reason or f"Unban by {ctx.author}")
        except discord.NotFound:
            return await ctx.send(":x: User is not banned")

        query = """DELETE FROM tasks
                   WHERE tasks.guild_id=$1 AND tasks.user_id=$2 AND tasks.task=$3;
                """
        await self.bot.db.execute(query, ctx.guild.id, user.id, "unban")

        await ctx.send(f":white_check_mark: Unbanned {user.id}")

    @commands.group(name="mute", description="Mute a member", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, user: discord.Member, *, reason=None):
        if user.id in ctx.guild_config["muted"]:
            return await ctx.send(":x: User is already muted")
        if not ctx.guild_config["mute_role_id"]:
            return await ctx.send(":x: No mute role set")

        if reason:
            reason = f"Mute by {ctx.author} with reason {reason}"
        role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])
        await user.add_roles(role, reason=reason or f"Mute by {ctx.author}")

        ctx.guild_config["muted"].append(user.id)

        query = """UPDATE guild_config
                   SET Muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, ctx.guild_config["muted"], ctx.guild.id)

        await ctx.send(f":white_check_mark: Muted {user}")

    @commands.command(name="tempmute", description="Temporarily mute a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def tempmute(self, ctx, user: discord.Member, time: TimeConverter, *, reason=None):
        if user.id in ctx.guild_config["muted"]:
            return await ctx.send(":x: User is already muted")
        if not ctx.guild_config["mute_role_id"]:
            return await ctx.send(":x: No mute role set")

        if reason:
            reason = f"Temporary mute by {ctx.author} with reason {reason}"
        role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])
        await user.add_roles(role, reason=reason or f"Temporary mute by {ctx.author}")

        ctx.guild_config["muted"].append(user.id)

        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, ctx.guild_config["muted"], ctx.guild.id)

        query = """INSERT INTO tasks (task, guild_id, channel_id, user_id, time)
                   VALUES ($1, $2, $3, $4, $5);
                """
        await self.bot.db.execute(query, "unmute", ctx.guild.id, ctx.channel.id, user.id, time)

        await ctx.send(f":white_check_mark: Muted {user} for {humanize.naturaldelta(time-datetime.datetime.utcnow())}")

    @commands.command(name="selfmute", description="Mute your self")
    @commands.bot_has_permissions(manage_roles=True)
    async def selfmute(self, ctx, time: TimeConverter, *, reason=None):
        if ctx.author.id in ctx.guild_config["muted"]:
            return await ctx.send(":x: You are already muted")
        if not ctx.guild_config["mute_role_id"]:
            return await ctx.send(":x: No mute role set")

        if reason:
            reason = f"Self mute with reason {reason}"
        role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])
        await ctx.author.add_roles(role, reason=reason or f"Self mute")

        ctx.guild_config["muted"].append(ctx.author.id)

        query = """UPDATE guild_config
                   SET muted=$1
                   WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, ctx.guild_config["muted"], ctx.guild.id)

        query = """INSERT INTO tasks (task, guild_id, channel_id, user_id, time)
                   VALUES ($1, $2, $3, $4, $5);
                """
        await self.bot.db.execute(query, "unmute", ctx.guild.id, ctx.channel.id, ctx.author.id, time)

        await ctx.send(f":white_check_mark: You are muted")

    @mute.group(name="role", invoke_without_command=True)
    async def mute_role(self, ctx):
        mute_role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])
        if not mute_role:
            return await ctx.send(":x: No mute role")
        role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])
        await ctx.send(f"The muted role for this server is `{role.name}` ({role.id})")

    @mute_role.command(name="set", description="Set the mute role")
    async def mute_role_set(self, ctx, role: discord.Role):
        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, role.id, [], ctx.guild.id)

        await ctx.send(":white_check_mark: Set mute role")

    @mute_role.command(name="create", description="Create a mute role")
    async def mute_role_create(self, ctx):
        reason = f"Create mute role by {ctx.author}"
        role = await ctx.guild.create_role(name="Muted", reason=reason)

        channels = ctx.guild.text_channels + ctx.guild.categories
        success = 0
        failed = 0

        for channel in channels:
            try:
                overwrite = discord.PermissionOverwrite()
                overwrite.send_messages = False
                overwrite.add_reactions = False
                await channel.set_permissions(role, overwrite=overwrite, reason=reason)
                success += 1
            except:
                failed += 1

        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, role.id, [], ctx.guild.id)

        await ctx.send(":white_check_mark: Created mute role")

    @mute_role.command(name="unbind", description="Unbind the current mute role")
    async def mute_role_unbind(self, ctx):
        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, None, [], ctx.guild.id)

        await ctx.send(":white_check_mark: Unbound mute role")

    @commands.command(name="unmute", description="Unmute a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, user: typing.Union[discord.Member, int], *, reason=None):
        if not ctx.guild_config["mute_role_id"]:
            return await ctx.send(":x: No mute role set")
        if reason:
            reason = f"Unmute by {ctx.author} with reason {reason}"
        role = ctx.guild.get_role(ctx.guild_config["mute_role_id"])

        if isinstance(user, discord.Member):
            if user.id not in ctx.guild_config["muted"]:
                return await ctx.send(":x: User is not muted")

            await user.remove_roles(role, reason=reason or f"Unmute by {ctx.author}")

            ctx.guild_config["muted"].remove(user.id)

            query = """UPDATE guild_config 
                       SET muted=$1
                       WHERE guild_config.guild_id=$2;
                    """
            await self.bot.db.execute(query, ctx.guild_config["muted"], ctx.guild.id)
    
            query = """DELETE FROM tasks
                       WHERE tasks.guild_id=$1 AND tasks.user_id=$2 AND tasks.task=$3;"""
            await self.bot.db.execute(query, ctx.guild.id, user.id, "unmute")
        else:
            if user not in ctx.guild_config["muted"]:
                return await ctx.send(":x: User is not muted")

            ctx.guild_config["muted"].remove(user)
            query = """UPDATE guild_config 
                       SET muted=$1
                       WHERE guild_config.guild_id=$2;
                    """
            await self.bot.db.execute(query, ctx.guild_config["muted"], ctx.guild.id)
    
            query = """DELETE FROM tasks
                       WHERE tasks.guild_id=$1 AND tasks.user_id=$2 AND tasks.task=$3;"""
            await self.bot.db.execute(query, ctx.guild.id, user, "unmute")

        await ctx.send(f":white_check_mark: Unmuted {user}")

    @commands.command(name="muted", description="View a list of muted members")
    @commands.has_permissions(manage_roles=True)
    async def muted(self, ctx):
        if not ctx.guild_config["muted"]:
            return await ctx.send("No muted members")

        msg = "```ini"
        for counter, muted_user in enumerate(ctx.guild_config["muted"]):
            user = ctx.guild.get_member(muted_user)
            if user:
                msg += f"\n[{counter+1}] {user} ({user.id})"
            else:
                msg += f"\n[{counter+1}] Not in server ({muted_user})"
        msg += "\n```"

        await ctx.send(msg)

    @commands.command(name="purge", description="Purge messages from a channel")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, limit: int = 100):
        deleted = await ctx.channel.purge(limit=limit+1)
        await ctx.send(f":white_check_mark: Deleted {len(deleted)} messages(s)", delete_after=5)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        query = """SELECT * FROM guild_config
                   WHERE guild_config.guild_id=$1;"""
        guild_config = await self.bot.db.fetchrow(query, member.guild.id)

        if guild_config and member.id in guild_config["muted"]:
            role = member.guild.get_role(guild_config["mute_role_id"])
            await member.add_roles(role, reason="Member was muted when they left")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        guild_config = await self.bot.db.fetchrow(query, role.guild.id)

        if guild_config["mute_role_id"] != role.id:
            return

        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, None, [], role.guild.id)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        guild_config = await self.bot.db.fetchrow(query, after.guild.id)

        if not guild_config or not guild_config["mute_role_id"]:
            return

        if after.id not in guild_config["muted"] and guild_config["mute_role_id"] in [x.id for x in after.roles]:
            guild_config["muted"].append(after.id)
            query = """UPDATE guild_config
                       SET muted=$1
                       WHERE guild_config.guild_id=$2;
                    """
            await self.bot.db.execute(query, guild_config["muted"], after.guild.id)

        if after.id in guild_config["muted"] and guild_config["mute_role_id"] not in [x.id for x in after.roles]:
            guild_config["muted"].remove(after.id)
            query = """UPDATE guild_config
                       SET muted=$1
                       WHERE guild_config.guild_id=$2;
                    """
            await self.bot.db.execute(query, guild_config["muted"], after.guild.id)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        query = """SELECT *
                   FROM guild_config
                   WHERE guild_config.guild_id=$1;
                """
        guild_config = await self.bot.db.fetchrow(query, role.guild.id)

        if not guild_config or guild_config["mute_role_id"] != role.id:
            return

        query = """UPDATE guild_config
                   SET mute_role_id=$1, muted=$2
                   WHERE guild_config.guild_id=$3;
                """
        await self.bot.db.execute(query, None, [], role.guild.id)

    @commands.Cog.listener()
    async def on_unban_task(self, task):
        guild = self.bot.get_guild(task["guild_id"])
        user = self.bot.get_user(task["user_id"])
        await guild.unban(discord.Object(id=task["user_id"]), reason="Temporary ban is over")

    @commands.Cog.listener()
    async def on_unmute_task(self, task):
        guild = self.bot.get_guild(task["guild_id"])

        query = """SELECT * FROM guild_config
                    WHERE guild_config.guild_id=$1;
                """
        guild_config = await self.bot.db.fetchrow(query, task["guild_id"])

        user = guild.get_member(task["user_id"])
        if user:
            role = guild.get_role(guild_config["mute_role_id"])
            await user.remove_roles(role, reason="Temporary mute is over")

        guild_config["muted"].remove(user.id)

        query = """UPDATE guild_config
                    SET muted=$1 WHERE guild_config.guild_id=$2;
                """
        await self.bot.db.execute(query, guild_config["muted"], task["guild_id"])

def setup(bot):
    bot.add_cog(Moderation(bot))