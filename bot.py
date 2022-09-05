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
        prefixes.extend(bot.prefixes.get(message.guild.id, bot.config.default_prefixes))
    else:
        prefixes.extend(bot.config.default_prefixes + ["!"])
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

class RoboCoder(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=False)

        super().__init__(command_prefix=get_prefix, description="A multipurpose Discord bot", case_insensitive=True, intents=intents, allowed_mentions=allowed_mentions)

        self.prefixes = config.Config("prefixes.json")
        self.translator = googletrans.Translator()
        self.players = {}
        self.console = None

    async def setup_hook(self):
        logging.info("Setting up bot...")

        # Load Jishaku
        log.info("Loading jishaku")
        await self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        # Load extensions
        log.info("Loading extensions")
        for extension in extensions:
            try:
                await self.load_extension(extension)
            except Exception as exc:
                log.info("Couldn't load extension %s", extension, exc_info=exc)

        # Create aiohttp session
        log.info("Starting aiohttp session")
        self.session = aiohttp.ClientSession()
        if self.config.status_hook:
            self.status_webhook = discord.Webhook.from_url(self.config.status_hook, adapter=discord.AsyncWebhookAdapter(self.session))

        # Create database connection
        log.info("Starting database connection")
        async def init(connection): await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)

        # Load emojis
        log.info("Loading emojis")
        with open("assets/emojis.json") as file:
            self.default_emojis = json.load(file)

        # Uptime
        log.info("Setup is complete; logging uptime")
        self.uptime = datetime.datetime.utcnow()

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")

        self.console = bot.get_channel(self.config.console)
        if self.config.status_hook:
            await self.status_webhook.send("Recevied READY event")

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
        super().run(self.config.token)

    async def close(self):
        log.info("Logged out of Discord")

        if self.config.status_hook:
            await self.status_webhook.send("Logging out of Discord")

        await self.stop_players()
        await self.db.close()
        await self.session.close()

        await super().close()

    def get_guild_prefix(self, guild):
        prefixes = self.prefixes.get(guild.id) or [self.user.mention]
        return prefixes[0]

    def get_guild_prefixes(self, guild):
        return self.prefixes.get(guild.id, self.config.default_prefixes)

    async def stop_players(self):
        player_count = len(self.players)
        log.info("Stopping %s players.", player_count)

        for player in self.players.copy().values():
            if player.queue:
                url = await player.save_queue(player)
                await player.ctx.send(f"Your player was automatically stopped for maintenance. Luckily, I saved the queue to {url}.")
            elif player.now:
                await player.ctx.send(f"Your player was automatically stopped for matinanace.")

            await player.cleanup()

        return player_count

    async def post_bin(self, content):
        async with self.session.post("https://hastebin.com/documents", data=content.encode("utf-8")) as resp:
            data = await resp.json()
            return f"<https://hastebin.com/{data['key']}>"

    @discord.utils.cached_property
    def config(self):
        return __import__("config")

bot = RoboCoder()
bot.run()
