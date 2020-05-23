import discord
from discord.ext import menus
from discord.ext import commands

import random

class Fun(commands.Cog):
    """Fun things for your server"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="reaction", description="Give the user a reaction", usage="[memberid] [emoji]")
    async def reaction(self, ctx, arg1, arg2):
        msg = await ctx.channel.fetch_message(int(arg1))
        emoji = discord.utils.get(self.bot.emojis, name=arg2)
        try:
            await msg.add_reaction(str(emoji))
            await ctx.send("Message reacted with: " + str(emoji))
        except:
            await msg.add_reaction(str(arg2))
            await ctx.send("Message reacted with: " + str(arg2))


    @commands.command(name="poll", description="Create a poll", usage="'[poll msg]' [reacton(s)]")
    async def poll(self, ctx, msg, *reactions):
        await ctx.send("Created new poll")
        em=discord.Embed(title="POLL")
        em.add_field(name=ctx.author, value=msg, inline=False)
        msg = await ctx.send(embed=em)
        for emoji in reactions:
            await msg.add_reaction(emoji)

    @commands.command(name="emoji", description="Find an emoji from any server the bot is on", usage="[emoji name]")
    async def detectemoji(self, ctx, *, emojitxt):
        emoji = discord.utils.get(self.bot.emojis, name=emojitxt)
        if emoji != None:
            await ctx.send(str(emoji))
    
    @commands.command(name="flipcoin", description="Flip a coin")
    async def flipcoin(self, ctx):
        await ctx.send(f"You got a {random.choice(['Head', 'Tail'])}")

    @commands.command(name="8ball", description="Use a 8 ball")
    async def magic8ball(self, ctx):
        await ctx.send(f"{random.choice(['Yes', 'No', 'Maybe'])}")

def setup(bot):
    bot.add_cog(Fun(bot))