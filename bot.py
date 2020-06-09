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
                if str(message.guild.id) in client.guild_prefixes.keys():
                    prefixes += client.guild_prefixes[str(message.guild.id)]
                else:
                    client.guild_prefixes[str(message.guild.id)] = ["r!"]
                    prefixes += client.guild_prefixes[str(message.guild.id)]
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
            owner_ids=self.config["ownerids"],
        )


        self.cogs_to_add = ["cogs.meta", "cogs.music", "cogs.tools", "cogs.moderation", "cogs.fun", "cogs.games", "cogs.notes", "cogs.reminders", "cogs.status"]

        self.loop.create_task(self.load_cogs_to_add())
        self.loop.create_task(self.on_start())
        self.startup_time = datetime.now()

    async def load_cogs_to_add(self):
        try:
            self.load_extension("jishaku")
            self.get_command("jishaku").hidden = True
        except Exception as e:
            print("Couldn't load jishaku")
        await self.wait_until_ready()
        self.remove_command('help')
        for cog in self.cogs_to_add:
            self.load_extension(cog)

    def run(self, token):
        super().run(token)


    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")
        for user in self.get_all_members():
            rows = rows = await self.db.fetch(f"SELECT Status, Time FROM Status_Updates WHERE Status_Updates.Userid='{user.id}';")
            if len(rows) != 0:
                if rows[-1][0] != str(user.status):
                    timestamp = datetime.now().timestamp()
                    await self.db.execute(f'''INSERT INTO Status_Updates(Userid, Status, Time) VALUES ($1, $2, $3)''', str(user.id), str(user.status), int(timestamp))


    async def on_start(self):
        #self.db = await asyncpg.connect(user=self.config["sqlname"], password=self.config["sqlpass"], database=self.config["dbname"], host='localhost')
        self.db = await asyncpg.create_pool(self.config["sqllogin"])
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS Notes(
                ID int,
                Userid text,
                Title text,
                Content text
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS Todo(
                ID int,
                Userid text,
                Content text,
                Status text
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS Reminders(
                ID int,
                Userid text,
                Guildid text,
                Channid text,
                Msgid text,
                Time int,
                Content text
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS Status_Updates(
                Userid text,
                Status text,
                Time int
            )
        ''')


bot = RoboCoder()
bot.run(bot.config["token"])
