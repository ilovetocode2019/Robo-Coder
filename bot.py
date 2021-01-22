import discord
from discord.ext import commands
from discord import Webhook, AsyncWebhookAdapter

import asyncpg
import aiohttp
import datetime
import logging
import traceback
import json

import config

log = logging.getLogger("robo_coder")

logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) %(levelname)s %(message)s",
    datefmt="%m/%d/%y - %H:%M:%S %Z"
)

def get_prefix(client, message):
    prefixes = ["r!"]
    if not isinstance(message.channel, discord.DMChannel) and hasattr(bot, "guild_prefixes"):
        if str(message.guild.id) in client.guild_prefixes.keys():
            prefixes = client.guild_prefixes[str(message.guild.id)]
        else:
            client.guild_prefixes[str(message.guild.id)] = ["r!"]

    return commands.when_mentioned_or(*prefixes)(client, message)

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

log.info("Starting")

class RoboCoder(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.presences = False
        super().__init__(command_prefix=get_prefix, description="A multipurpose Discord bot.", case_insensitive=True, intents=intents)
        self.loop.create_task(self.prepare_bot())

        self.config = config
        self.startup_time = datetime.datetime.utcnow()
        self.support_server_link = "https://discord.gg/eHxvStNJb7"
        self.players = {}
        self.spam_detectors = {}

        log.info("Loading extensions")
        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for cog in extensions:
            try:
                self.load_extension(cog)
            except Exception as exc:
                log.info(f"Couldn't load {cog}")
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

    async def prepare_bot(self):
        log.info("Creating aiohttp session")
        self.session = aiohttp.ClientSession(loop=self.loop)
        if config.status_hook:
            self.status_webhook = Webhook.from_url(config.status_hook, adapter=AsyncWebhookAdapter(self.session))

        log.info("Loading emojis")
        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

        log.info("Creating database pool")

        async def init(conn):
            await conn.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(config.database_uri, init=init)

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

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")

        self.console = bot.get_channel(config.console)
        if config.status_hook:
            await self.status_webhook.send("Recevied READY event")

    async def on_connect(self):
        if config.status_hook:
            await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        if config.status_hook and not self.session.closed:
            await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        if config.status_hook:
            await self.status_webhook.send("Resumed connection with Discord")

    async def stop_players(self):
        for player in self.players.copy().values():
            if player.queue:
                url = await player.save_queue(player)
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start again with r!playbin {url}.")
            elif player.now:
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start your song again with the play command.")

            await player.cleanup()

    async def post_bin(self, content):
        async with self.session.post("https://mystb.in/documents", data=content.encode("utf-8")) as resp:
            data = await resp.json()
            return f"https://mystb.in/{data['key']}"

    def run(self):
        super().run(config.token)

    async def logout(self):
        log.info("Logging out of Discord")

        if config.status_hook:
            await self.status_webhook.send("Logging out of Discord")

        await self.stop_players()
        await self.db.close()
        await self.session.close()
        await super().logout()

bot = RoboCoder()
bot.run()
