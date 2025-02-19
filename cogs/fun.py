import discord
from discord.ext import commands

import random

from .utils import formats


class Fun(commands.Cog):
    """Surprisingly entertaining random generators."""

    emoji = "\N{PARTY POPPER}"

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Flips a virtual coin to help you make a decision")
    async def flipcoin(self, ctx):
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f":coin: You flipped {result}")

    @commands.hybrid_command(description="Rolls some custom die", aliases=["rolldice"])
    async def rolldie(self, ctx, die: commands.Range[int, 1, 10] = 1, sides: commands.Range[int, 2, 100] = 6):
        numbers = [str(random.randint(1, sides)) for x in range(die)]
        await ctx.send(f":game_die: You rolled {formats.join(numbers, last="and")}")

    @commands.hybrid_command(name="8ball", description="Answers whatever question you'd like", aliases=["eightball"])
    async def eightball(self, ctx, *, question):
        choice = random.choice([
            "Yes",
            "Certainly",
            "Obviously",
            "Of course",
            "For sure",
            "Without a doubt",
            "It's likely"
            "No",
            "Nope",
            "No way"
            "Not a change",
            "Definitely not",
            "Obviously not",
            "Certainly not",
            "It's unlikely",
            "Maybe",
            "Quite possibly",
            "There is a chance",
            "It could go either way",
            "It's possible"
        ])
        await ctx.reply(choice)

    @commands.command(name="choose", description="Choose a random option", aliases=["choice"])
    async def choose(self, ctx, *options):
        if len(options) < 2:
            return await ctx.send("\N{CROSS MARK} You must specify at least two choices")

        choice = random.choice(options)
        await ctx.send(choice)


async def setup(bot):
    await bot.add_cog(Fun(bot))
