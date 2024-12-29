import discord
from discord import app_commands
from discord.ext import commands

import aiohttp
import asyncpg
import datetime
import json
import logging
import sys

from cogs.utils import config

log = logging.getLogger("robo_coder")
logging.basicConfig(level=logging.INFO, format="(%(asctime)s) %(levelname)s %(message)s", datefmt="%m/%d/%y - %H:%M:%S %Z")

def get_prefix(bot, message):
    default_prefixes = getattr(bot.config, "default_prefixes", ["r!", "r."])

    prefixes = [f"<@!{bot.user.id}> ", f"<@{bot.user.id}> "]
    if message.guild:
        prefixes.extend(bot.prefixes.get(message.guild.id, default_prefixes))
    else:
        prefixes.extend(default_prefixes + ["!"])
    return prefixes

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
    "cogs.tools"
]

class RoboCoderTree(app_commands.CommandTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            description="A multipurpose Discord bot",
            case_insensitive=True,
            intents=intents,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                users=True,
                roles=False,
                replied_user=False
            ),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
            allowed_contexts=app_commands.AppCommandContext(
                guild=True,
                dm_channel=True,
                private_channel=True
            ),
            tree_cls=RoboCoderTree
        )

        self.prefixes = config.Config("prefixes.json")
        self.support_server_invite = "https://discord.gg/6jQpPeEtQM"
        self.players = {}
        self.status_webhook = None
        self.console = None

    async def setup_hook(self):
        logging.info("Setting up bot now")

        await self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        self.session = aiohttp.ClientSession()
        async def init(connection): await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)
        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

        if getattr(self.config, "status_hook", None):
            self.status_webhook = discord.Webhook.from_url(self.config.status_hook, session=self.session)
        if getattr(self.config, "console_hook", None):
            self.console = discord.Webhook.from_url(self.config.console_hook, session=self.session)

        self.uptime = discord.utils.utcnow()

        for extension in extensions:
            try:
                await self.load_extension(extension)
            except Exception as exc:
                log.info("Couldn't load extension %s", extension, exc_info=exc)

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")

        if self.status_webhook:
            await self.status_webhook.send("Received guilds from Discord")

    async def on_connect(self):
        if self.status_webhook:
            await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        if self.status_webhook and not self.session.closed:
            await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        if self.status_webhook:
            await self.status_webhook.send("Resumed connection with Discord")

    def run(self):
        super().run(self.config.token)

    async def close(self):
        log.info("Logged out of Discord")

        if self.status_webhook:
            await self.status_webhook.send("Logging out of Discord")

        await self.stop_players()
        await self.db.close()
        await self.session.close()

        await super().close()

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
