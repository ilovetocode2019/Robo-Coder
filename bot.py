import json
import logging
from datetime import datetime

import discord
from discord.ext import commands
import os
import pathlib
import asyncpg

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
    prefixes = []
    try:
        if client.get_cog("Meta"):

            if not isinstance(message.channel, discord.DMChannel):
                if str(message.guild.id) in client.customization.keys():
                    prefixes += client.customization[str(message.guild.id)]["prefixes"]
                else:
                    client.customization[str(message.guild.id)] = {"prefixes":["r!"], "color": (46, 184, 76)}
            else:
                prefixes = ["r!"]

        else:

            prefixes = ["r!"]
    except Exception as e:
        print(e)
            

    return commands.when_mentioned_or(*prefixes)(client, message)

class RoboCoder(commands.Bot):
    def __init__(self):
        with open("config.json", "r") as f:
            self.config = json.load(f)
        super().__init__(
            command_prefix = get_prefix,
            description = "A discord bot with tools, fun and coding related stuff.",
            case_insensitive=True,
            owner_id=self.config["dev"],
        )

        self.cogs_to_add = ["cogs.meta", "cogs.music", "cogs.tools", "cogs.moderation", "cogs.fun", "cogs.games", "cogs.notes", "cogs.reminders", "cogs.stats"]

        self.loop.create_task(self.load_cogs_to_add())
        self.loop.create_task(self.on_start())
        
        self.connected_at = "Not connected yet..."
        self.startup_time = datetime.now()

    async def load_cogs_to_add(self):
        try:
            self.load_extension("jishaku")
            self.get_command("jishaku").hidden = True
        except Exception as e:
            print("Couldn't load jishaku")
        self.remove_command('help')
        for cog in self.cogs_to_add:
            self.load_extension(cog)

    def run(self, token):
        super().run(token)


    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")


    async def on_start(self):
        #self.db = await asyncpg.connect(user=self.config["sqlname"], password=self.config["sqlpass"], database=self.config["dbname"], host='localhost')
        self.db = await asyncpg.create_pool(self.config["sqllogin"])
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS notes(
                id serial PRIMARY KEY,
                userid text,
                title text,
                content text
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS todo(
                id serial PRIMARY KEY,
                userid text,
                content text,
                status text
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS reminders(
                id serial PRIMARY KEY,
                userid text,
                guildid text,
                channid text,
                msgid text,
                time int,
                content text
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS commands(
                userid text,
                guildid text,
                command text,
                time int
            )
        ''')

bot = RoboCoder()
bot.run(bot.config["token"])
