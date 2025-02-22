import discord
from discord import app_commands
from discord.ext import commands


import aiohttp
import asyncpg
import datetime
import json
import logging
import sys
import time

from cogs.utils import config

log = logging.getLogger("robo_coder")
logging.basicConfig(level=logging.INFO, format="(%(asctime)s) %(levelname)s %(message)s", datefmt="%m/%d/%y - %H:%M:%S %Z")

extensions = [
    "cogs.admin",
    "cogs.fun",
    "cogs.games",
    "cogs.internet",
    "cogs.meta",
    "cogs.moderation",
    "cogs.music",
    "cogs.roles",
    "cogs.timers",
    "cogs.tools",
    "cogs.logging"
]


def get_prefix(bot, message):
    default_prefixes = getattr(bot.config, "default_prefixes", ["r!", "r."])

    prefixes = [f"<@!{bot.user.id}> ", f"<@{bot.user.id}> "]
    if message.guild:
        prefixes.extend(bot.prefixes.get(message.guild.id, default_prefixes))
    else:
        prefixes.extend(default_prefixes + ["!"])
    return prefixes


class RoboCoderTree(app_commands.CommandTree):
    def __init__(self, client):
        super().__init__(
            client,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
        )
        self._cached_commands = {}

    async def sync(self, *, guild = None):
        commands = await super().sync(guild=guild)
        self._cached_commands[guild.id if guild else None] = commands
        return commands

    async def fetch_commands(self, *, guild = None):
        commands = await super().fetch_commands(guild=guild)
        self._cached_commands[guild.id if guild else None] = commands
        return commands

    async def mention_for(self, name, *, guild = None):
        if guild not in self._cached_commands:
            await self.fetch_commands(guild=guild)

        command = discord.utils.get(self._cached_commands[guild], name=name)
        return command.mention if command else None


class RoboCoder(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.presences = False
        intents.typing = False

        super().__init__(
            command_prefix=get_prefix,
            description="A multipurpose bot. Likes to code for fun.",
            case_insensitive=True,
            intents=intents,
            allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=False),
            tree_cls=RoboCoderTree
        )

        self.support_server_invite = "https://discord.gg/6jQpPeEtQM"
        self.players = {}

        self.global_cooldowns = {}

    async def setup_hook(self):
        self.prefixes = config.Config("prefixes.json")
        self.blacklist = config.Config("blacklist.json")
        self.uptime = discord.utils.utcnow()
        self.session = aiohttp.ClientSession()

        if self.config.console_webhook_url is not None:
            self.console = discord.Webhook.from_url(self.config.console_webhook_url, session=self.session)
        else:
            self.console = None

        async def init(connection):
            await connection.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=json.dumps,
                decoder=json.loads,
                format="text"
            )
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)

        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

        await self.load_extension("jishaku")

        for extension in extensions:
            try:
                await self.load_extension(extension)
            except Exception as exc:
                log.info("Failure while loading extension %s.", extension, exc_info=exc)

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}.")

    async def on_guild_join(self):
        if guild.id in self.blacklist:
            await guild.leave()

    async def get_blacklisted(self, resource):
        blacklisted = self.blacklist.get(resource.id)

        if blacklisted is not True and blacklisted is not None and time.time() > blacklisted:
            await self.blacklist.remove(resource.id)
        else:
            return blacklisted

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message)

        if not ctx.valid:
            return

        if message.author.id != self.owner_id:
            if await self.get_blacklisted(message.author) is not None:
                return log.warning("Ignoring command from blacklisted user %s (%s).", message.author.name, message.author.id)
            if message.guild is not None and await self.get_blacklisted(message.guild) is not None:
                return log.warning("Ignoring command in blacklisted guild %s (%s).", message.guild.name, message.guild.id)

            if message.author.id not in self.global_cooldowns:
                self.global_cooldowns[message.author.id] = commands.Cooldown(rate=15, per=12)

            cooldown = self.global_cooldowns[message.author.id]
            cooldown.update_rate_limit(message.created_at.timestamp())
            tokens = cooldown.get_tokens(message.created_at.timestamp())

            if tokens == 0:
                log.warning("User %s (%s) has been permanently blacklisted for spamming.", message.author.name, message.author.id)
                await self.blacklist.add(message.author.id, True)
                return await message.reply(
                    f"You are now permanently blacklisted. You may appeal "
                    f"[here](<{self.support_server_invite}>), **only** with a legitimate reason."
                )
            elif tokens == 5:
                retry_after = int(cooldown.per - (message.created_at.timestamp() - cooldown._window)) + 1
                log.warning("User %s (%s) is being ratelimited for spamming with %s seconds remaining.", message.author.name, message.author.id, retry_after)
                return await message.reply(
                    f"You are now on global cooldown for {retry_after} more seconds "
                    "as a result of spamming. "
                    "You will be permanently blacklisted from using commands if you continue."
                )
            elif tokens < 5:
                return

            # remove "dead" cooldowns
            for user_id, cooldown in self.global_cooldowns.copy().items():
                if message.created_at.timestamp() > cooldown._last + cooldown.per:
                    del self.global_cooldowns[user_id]

        await self.invoke(ctx)

    async def close(self):
        await self.stop_players()
        await self.db.close()
        await self.session.close()
        await super().close()

    def run(self):
        super().run(self.config.token)

    def get_guild_prefix(self, guild_id):
        prefixes = self.get_guild_prefixes(guild_id) or [self.user.mention]
        return prefixes[0]

    def get_guild_prefixes(self, guild_id):
        return self.prefixes.get(guild_id, getattr(self.config, "default_prefixes", ["r!", "r."]))

    async def stop_players(self):
        player_count = len(self.players)
        log.info("Stopping %s player(s).", player_count)

        for player in self.players.copy().values():
            await player.cleanup()

        return player_count

    @discord.utils.cached_property
    def config(self):
        return __import__("config")

bot = RoboCoder()
bot.run()
