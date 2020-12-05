import discord
from discord.ext import commands

import dateparser

class TimeConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            if not arg.startswith("in") and not arg.startswith("at"):
                arg = f"in {arg}"
            time = dateparser.parse(arg, settings={"TIMEZONE": "UTC"})
        except:
            raise commands.BadArgument("Failed to parse time")
        if not time:
            raise commands.BadArgument("Failed to parse time")
        return time
