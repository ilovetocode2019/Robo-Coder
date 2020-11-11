import discord
from discord.ext import commands

import random

class Fun(commands.Cog):
    """Fun commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":tada:"

    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcion(self, ctx):
        await ctx.send(random.choice(["Heads", "Tails"]))

    @commands.command(name="random", description="Choose a random option", aliases=["choose", "which", "select"])
    async def select(self, ctx, *options):
        await ctx.send(random.choice(options))

    @commands.command(name="rolldice", description="Role some dice")
    async def rolldice(self, ctx, dice=1, sides=6):
        numbers = [str(random.randint(1, sides)) for x in range(dice)]
        if len(numbers) == 1:
            dice_str = str(numbers[0])
        else:
            dice_str = f"{', '.join(numbers[:-1])} and a {numbers[-1]}"
        await ctx.send(f"You roled a {dice_str}")

    @commands.command(name="question", description="Ask me a question", aliases=["yesno", "8ball"])
    async def question(self, ctx, *, question):
        await ctx.send(random.choice(["Yes", "No", "Maybe"]))

def setup(bot):
    bot.add_cog(Fun(bot))
