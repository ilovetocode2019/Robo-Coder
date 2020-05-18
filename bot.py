import json
import logging
from datetime import datetime

import discord
from discord.ext import commands
import os
import pathlib
import aiosqlite
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

    if not isinstance(message.channel, discord.DMChannel):
        if str(message.guild.id) in client.guild_prefixes.keys():
            prefixes += client.guild_prefixes[str(message.guild.id)]
        else:
            client.guild_prefixes[str(message.guild.id)] = ["r!"]
            prefixes += client.guild_prefixes[str(message.guild.id)]
    else:
        prefixes = ["r!"]
        

    return commands.when_mentioned_or(*prefixes)(client, message)

class RoboCoder(commands.Bot):
    def __init__(self):
        with open("config.json", "r") as f:
            self.config = json.load(f)
        super().__init__(
            command_prefix = get_prefix,
            description = "A bot to chat with",
            case_insensitive=True,
            owner_ids=self.config["ownerids"],
        )


        self.cogs_to_add = ["cogs.meta", "cogs.conversation", "cogs.mail", "cogs.status", "cogs.music", "cogs.tools", "cogs.moderation", "cogs.fun", "cogs.games", "cogs.notes", "cogs.reminders"]

        self.loop.create_task(self.load_cogs_to_add())

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
        self.startup_time = datetime.now()
        path = pathlib.Path("data.db")
        self.db = await aiosqlite.connect(path)
        await self.db.execute("CREATE TABLE IF NOT EXISTS Notes('ID', 'Title', 'Content')")
        await self.db.execute("CREATE TABLE IF NOT EXISTS Reminders('Userid', 'Guildid', 'Channid', 'Msgid', 'Time' int, 'Content')")

bot = RoboCoder()
bot.run(bot.config["token"])
