import discord
from discord.ext import menus
from discord.ext import commands

import random

from .utils import custom

class Fun(commands.Cog):
    """Fun commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":tada:"
        self.hidden = True

    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcoin(self, ctx):
        await ctx.send(f"You got a {random.choice(['head', 'tail'])}")

    @commands.command(name="8ball", description="Use a 8 ball")
    async def magic8ball(self, ctx):
        await ctx.send(f"{random.choice(['Yes', 'No', 'Maybe'])}")
    
    @commands.command(name="embed", description="Create a simple embed")
    async def embed(self, ctx, title, *, msg):
        em = self.bot.build_embed(title=title, description=msg)
        em.set_author(name=str(ctx.author.display_name), icon_url=ctx.author.avatar_url)
        em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        msg = await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Fun(bot))