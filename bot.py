import json
import logging
from datetime import datetime

import discord
from discord.ext import commands
from discord import Webhook, AsyncWebhookAdapter

import os
import pathlib
import asyncpg
import aiohttp

from cogs.utils import custom
from cogs.utils import context

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="coder.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

logging.basicConfig(

    level = logging.INFO,
    format = "(%(asctime)s) %(levelname)s %(message)s",
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
        with open("config.json", "r") as f:
            self.config = json.load(f)
        super().__init__(
            command_prefix = get_prefix,
            description = "A discord bot with tools, fun, and coding related stuff.",
            case_insensitive=True,
            owner_id=self.config["dev"],
            intents=discord.Intents.all()
        )

        self.loop.create_task(self.load_extensions())
        self.loop.create_task(self.setup_bot())
        self.startup_time = datetime.now()

    async def load_extensions(self):
        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for cog in extensions:
            self.load_extension(cog)

    def run(self, token):
        super().run(token)

    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")

    async def setup_bot(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.status_webhook = Webhook.from_url(self.config["webhook"], adapter=AsyncWebhookAdapter(self.session))

        async def init(conn):
            await conn.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=json.dumps,
                decoder=json.loads,
                format="text",
            )
        self.db = await asyncpg.create_pool(self.config["sqllogin"], init=init)

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

    async def on_connect(self):
        await self.status_webhook.send("Connected to Discord")

    async def on_disconnect(self):
        await self.status_webhook.send("Disconnected from Discord")

    async def on_resumed(self):
        await self.status_webhook.send("Resumed connection with to Discord")

    def build_embed(self, **embed_kwargs):
        if "color" not in embed_kwargs:
            embed_kwargs["color"] = custom.Color.default
        
        em = discord.Embed(**embed_kwargs)
        return em

bot = RoboCoder()
bot.run(bot.config["token"])
