import discord
from discord.ext import menus
from discord.ext import commands

import random

class Fun(commands.Cog):
    """Fun things for your server"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="emoji", description="Find an emoji from any server the bot is on", usage="[emoji name]")
    async def detectemoji(self, ctx, *, emojitxt):
        emoji = discord.utils.get(self.bot.emojis, name=emojitxt)
        if emoji != None:
            await ctx.send(str(emoji))
    
    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcoin(self, ctx):
        await ctx.send(f"You got a {random.choice(['head', 'tail'])}")

    @commands.command(name="8ball", description="Use a 8 ball")
    async def magic8ball(self, ctx):
        await ctx.send(f"{random.choice(['Yes', 'No', 'Maybe'])}")
    
    @commands.command(name="embed", description="Create a simple embed")
    async def embed(self, ctx, title, *, msg):
        em = discord.Embed(title=title, description=msg, color=0x00ff00)
        em.set_author(name=str(ctx.author.display_name), icon_url=ctx.author.avatar_url)
        em.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        msg = await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Fun(bot))