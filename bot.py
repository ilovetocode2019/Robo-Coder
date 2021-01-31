import discord
from discord.ext import commands
from discord import Webhook, AsyncWebhookAdapter

import asyncpg
import aiohttp
import datetime
import logging
import traceback
import json

from cogs.utils.config import Config

log = logging.getLogger("robo_coder")
logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) %(levelname)s %(message)s",
    datefmt="%m/%d/%y - %H:%M:%S %Z"
)

log.info("Starting Robo Coder")

extensions = [
"cogs.meta",
"cogs.admin",
"cogs.tools",
"cogs.internet",
"cogs.moderation",
"cogs.fun",
"cogs.games",
"cogs.timers",
"cogs.music",
"cogs.roles"
]

def get_prefix(bot, message):
    prefixes = [f"<@!{bot.user.id}> ", f"<@{bot.user.id}> "]
    if message.guild:
        prefixes.extend(bot.prefixes.get(message.guild.id, ["r!", "r."]))
    else:
        prefixes.extend(["r!", "r.", "!"])
    return prefixes

class RoboCoder(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix=get_prefix, description="A multipurpose Discord bot.", case_insensitive=True, intents=intents)

        self.support_server_link = "https://discord.gg/eHxvStNJb7"
        self.players = {}
        self.spam_detectors = {}

        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for cog in extensions:
            try:
                self.load_extension(cog)
            except Exception as exc:
                log.info(f"Couldn't load {cog}")
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

        log.info("Loading prefixes")
        self.prefixes = Config("prefixes.json", loop=self.loop)

        log.info("Creating aiohttp session")
        self.session = aiohttp.ClientSession(loop=self.loop)
        if self.config.status_hook:
            self.status_webhook = Webhook.from_url(self.config.status_hook, adapter=AsyncWebhookAdapter(self.session))

        log.info("Loading emojis")
        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

    async def create_pool(self):
        async def init(conn):
            await conn.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        query = """CREATE TABLE IF NOT EXISTS guild_config (
                   guild_id BIGINT PRIMARY KEY,
                   mute_role_id BIGINT,
                   muted BIGINT ARRAY,
                   spam_prevention BOOL,
                   ignore_spam_channels BIGINT ARRAY,
                   log_channel_id BIGINT
                   );

                   CREATE TABLE IF NOT EXISTS timers (
                   id SERIAL PRIMARY KEY,
                   event TEXT,
                   data jsonb DEFAULT ('{}'::jsonb),
                   expires_at TIMESTAMP,
                   created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
                   );

                   CREATE TABLE IF NOT EXISTS autoroles (
                   guild_id BIGINT,
                   role_id BIGINT PRIMARY KEY
                   );

                   CREATE TABLE IF NOT EXISTS songs (
                   id SERIAL PRIMARY KEY,
                   song_id TEXT,
                   title TEXT,
                   filename TEXT,
                   extractor TEXT,
                   plays INT,
                   data jsonb DEFAULT ('{}'::jsonb),
                   created_at TIMESTAMP DEFAULT (now() at time zone 'utc'),
                   updated_at TIMESTAMP DEFAULT (now() at time zone 'utc')
                   );

                   CREATE TABLE IF NOT EXISTS song_searches (
                   search TEXT PRIMARY KEY,
                   song_id INT,
                   expires_at TIMESTAMP
                   );

                   CREATE UNIQUE INDEX IF NOT EXISTS unique_songs_index ON songs (song_id, extractor);
                """
        await self.db.execute(query)

    def get_guild_prefix(self, guild):
        return self.prefixes.get(guild.id, [self.user.mention])[0]

    def get_guild_prefixes(self, guild):
        return self.prefixes.get(guild.id, ["r!", "r."])

    async def post_bin(self, content):
        async with self.session.post("https://mystb.in/documents", data=content.encode("utf-8")) as resp:
            data = await resp.json()
            return f"https://mystb.in/{data['key']}"

    async def get_bin(self, url):
        parsed = urllib.parse.urlparse(url)
        newpath = "/raw" + parsed.path
        url = parsed.scheme + "://" + parsed.netloc + newpath
        async with self.bot.session.get(url) as response:
            data = await response.read()
            data = data.decode("utf-8")
            return data.split("\n")

    async def on_ready(self):
        if not hasattr(self, "db"):
            self.db = await self.create_pool()
        if not hasattr(self, "uptime"):
            self.uptime = datetime.datetime.utcnow()

        self.console = bot.get_channel(self.config.console)
        if self.config.status_hook:
            await self.status_webhook.send("Logged into Discord")

        log.info(f"Logged in as {self.user.name} - {self.user.id}")

    async def on_connect(self):
        if self.config.status_hook:
            await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        if self.config.status_hook and not self.session.closed:
            await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        if self.config.status_hook:
            await self.status_webhook.send("Resumed connection with Discord")

    def run(self):
        log.info("Running bot")
        super().run(self.config.token)

    async def logout(self):
        log.info("Logging out of Discord")

        if self.config.status_hook:
            await self.status_webhook.send("Logging out of Discord")

        music = self.bot.get_cog("Music"):
        if music:
            await self.stop_players()

        await self.db.close()
        await self.session.close()
        await super().logout()

    @property
    def config(self):
        return __import__("config")

bot = RoboCoder()
bot.run()
