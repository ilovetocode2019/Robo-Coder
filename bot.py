import discord
from discord.ext import commands
from discord import Webhook, AsyncWebhookAdapter

import asyncpg
import aiohttp
import datetime
import logging
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
"cogs.timers"
]

class RoboCoder(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, description="A multipurpose Discord bot.", case_insensitive=True, owner_id=config.owner_id, intents=discord.Intents.all())
        self.loop.create_task(self.prepare_bot())
        self.startup_time = datetime.datetime.utcnow()

        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for cog in extensions:
            self.load_extension(cog)

    async def prepare_bot(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.status_webhook = Webhook.from_url(config.status_hook, adapter=AsyncWebhookAdapter(self.session))

        async def init(conn):
            await conn.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=json.dumps,
                decoder=json.loads,
                format="text",
            )
        self.db = await asyncpg.create_pool(config.database_uri, init=init)

        query = """CREATE TABLE IF NOT EXISTS guild_config (
                   ID SERIAL PRIMARY KEY,
                   guild_id BIGINT,
                   mute_role_id BIGINT,
                   muted bigint ARRAY
                   );

                   CREATE TABLE IF NOT EXISTS timers (
                   id SERIAL PRIMARY KEY,
                   event TEXT,
                   time TIMESTAMP,
                   extra jsonb DEFAULT ('{}'::jsonb),
                   created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
                   );
                """
        await self.db.execute(query)

    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")
        await self.status_webhook("Logged into Discord")

    async def on_connect(self):
        await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        await self.status_webhook.send("Resumed connection with to Discord")

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")
        await self.status_webhook.send("Recevied READY event")

    def run(self):
        super().run(config.token)

    async def logout(self):
        await super().logout()
        await self.status_webhook.send("Logging out of Discord")
        await self.db.close()
        await self.session.close()

bot = RoboCoder()
bot.run()
