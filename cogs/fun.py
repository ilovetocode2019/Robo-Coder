import random

from discord.ext import commands

from .utils import formats

class Fun(commands.Cog):
    """Fun commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":tada:"

    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcoin(self, ctx):
        result = random.choice(["Heads", "Tails"])
        await ctx.send(f":coin: You flipped {result}")

    @commands.command(name="rolldice", description="Role some dice", aliases=["rolldie"])
    async def rolldice(self, ctx, dice=1, sides=6):
        if not dice:
            return await ctx.send(":x: You must roll at least 1 die")
        elif not sides:
            return await ctx.send(":x: Your dice must have sides")

        if dice > 10:
            return await ctx.send(":x: You can't roll more than 10 dice")
        elif dice > 100:
            return await ctx.send(":x: Your dice can't have more than 100 sides") 

        numbers = [str(random.randint(1, sides)) for x in range(dice)]
        await ctx.send(f":game_die: You rolled {formats.join(numbers)}")

    @commands.command(name="8ball", description="Ask me a question", aliases=["eightball"])
    async def eightball(self, ctx, *, question):
        choice = random.choice(
            [
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
                "Certinaly not",
                "It's unlikely",
                "Maybe",
                "Quite possibly",
                "There is a chance",
                "It could go either way",
                "It's possible",
            ]
        )

        await ctx.send(formats.quote(ctx.message, choice, quote=question))

    @commands.command(name="choose", description="Choose a random option")
    async def choose(self, ctx, *options):
        if not options:
            return await ctx.send(":x: You must specify options to choose from")

        choice = random.choice(options)
        await ctx.send(choice)

def setup(bot):
    bot.add_cog(Fun(bot))
