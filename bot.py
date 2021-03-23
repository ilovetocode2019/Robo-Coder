import discord
from discord.ext import commands

import aiohttp
import asyncpg
import datetime
import googletrans
import json
import logging
import sys

from cogs.utils import config

log = logging.getLogger("robo_coder")
logging.basicConfig(level=logging.INFO, format="(%(asctime)s) %(levelname)s %(message)s", datefmt="%m/%d/%y - %H:%M:%S %Z")

def get_prefix(bot, message):
    prefixes = [f"<@!{bot.user.id}> ", f"<@{bot.user.id}> "]
    if message.guild:
        prefixes.extend(bot.prefixes.get(message.guild.id, ["r!", "r."]))
    else:
        prefixes.extend(["r!", "r.", "!"])
    return prefixes

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

class RoboCoder(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix=get_prefix, description="A multipurpose Discord bot", case_insensitive=True, intents=intents)

        self.support_server_link = "https://discord.gg/eHxvStNJb7"
        self.uptime = datetime.datetime.utcnow()
        self.prefixes = config.Config("prefixes.json", loop=self.loop)
        self.translator = googletrans.Translator()
        self.players = {}
        self.spam_detectors = {}

        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for extension in extensions:
            try:
                self.load_extension(extension)
            except Exception as exc:
                log.info("Couldn't load extension %s", extension, exc_info=exc)

    async def create_pool(self):
        async def init(connection): await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)

    async def create_session(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        if self.config.status_hook:
            self.status_webhook = discord.Webhook.from_url(self.config.status_hook, adapter=discord.AsyncWebhookAdapter(self.session))

    def get_guild_prefix(self, guild):
        return self.prefixes.get(guild.id, [self.user.mention])[0]

    def get_guild_prefixes(self, guild):
        return self.prefixes.get(guild.id, ["r!", "r."])

    async def stop_players(self):
        for player in self.players.copy().values():
            if player.queue:
                url = await player.save_queue(player)
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start again with {player.ctx.prefix}playbin {url}.")

            elif player.now:
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start your song again with the play command.")

            await player.cleanup()

    async def post_bin(self, content):
        async with self.session.post("https://mystb.in/documents", data=content.encode("utf-8")) as resp:
            data = await resp.json()
            return f"https://mystb.in/{data['key']}"

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")

        self.console = bot.get_channel(self.config.console)
        if self.config.status_hook:
            await self.status_webhook.send("Recevied READY event")

    async def on_connect(self):
        if not hasattr(self, "session"):
            await self.create_session()

        if not hasattr(self, "db"):
            await self.create_pool()

        if self.config.status_hook:
            await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        if self.config.status_hook and not self.session.closed:
            await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        if self.config.status_hook:
            await self.status_webhook.send("Resumed connection with Discord")

    def run(self):
        super().run(self.config.token)

    async def logout(self):
        log.info("Logging out of Discord")

        if self.config.status_hook:
            await self.status_webhook.send("Logging out of Discord")

        await self.stop_players()
        await self.db.close()
        await self.session.close()
        await super().logout()

    @discord.utils.cached_property
    def config(self):
        return __import__("config")

bot = RoboCoder()
bot.run()
