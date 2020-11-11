import discord
from discord.ext import commands

import random

class Fun(commands.Cog):
    """Fun commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":tada:"

    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcoin(self, ctx):
        await ctx.send(f"You got a {random.choice(['head', 'tail'])}")

    @commands.command(name="8ball", description="Use a 8 ball")
    async def magic8ball(self, ctx):
        await ctx.send(f"{random.choice(['Yes', 'No', 'Maybe'])}")
    
def setup(bot):
    bot.add_cog(Fun(bot))
