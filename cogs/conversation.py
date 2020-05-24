from discord.ext import commands
import discord
from asyncio import sleep
from datetime import datetime
from .utils import detectors
import importlib


class Conversation(commands.Cog):
    """Have fun conversations with the bot"""
    def __init__(self, bot):
        self.bot = bot

    
    @commands.command(name="meaning", description="Get the meaning of internet slang", usage="[word]")
    async def meaning(self, ctx, arg):
        terms = {"rn":"right now", "brb":"be right back", "wdym":"what do you mean", "idc":"I don't care", "idk":"I don't know", "ttyl":"talk to you later", "btw":"by the way", "gtg": "got to go", "iirc":"if I recall correctly", "imo":"in my opinion", "lol":"laugh out loud", "ik":"I know", "ig":"I guess", "og":"original"}
        if arg in terms:
            await ctx.send(terms[arg])
        else:
            await ctx.send("sorry. We don't have this word yet")
    

    @commands.command(name="hello", description="Talk to me", aliases=["hi"])
    async def hello(self, ctx):
        def check(ms):
            # Look for the message sent in the same channel where the command was used
            # As well as by the user who used the command.
            return ms.channel == ctx.channel and ms.author == ctx.author
        await ctx.trigger_typing()
        await sleep(3)
        await ctx.send("How are you?")
        msg = await self.bot.wait_for("message", check = check)
        response = msg.content.lower()
        await ctx.trigger_typing()
        await sleep(3)
        feeling = detectors.emotion_finder(response.lower())
        if feeling == "good":
            await ctx.send("Good to hear!")
        elif feeling == "bad":
            await ctx.send("OH! sorry to hear that")
        elif feeling == "okay":
            await ctx.send("I am glad you are just okay")
        elif feeling == "relaxed":
            await ctx.send("I am glad you are relaxed! Enjoy your relaxation")
        elif feeling == "mad":
            await ctx.send("Take a deep breath, and calm down!")
        else:
            await ctx.send(feeling)
        if detectors.howAreYou_detecting(response.lower()):
            await ctx.trigger_typing()
            await sleep(3)
            await ctx.send("Me? I am good")
        await ctx.trigger_typing()
        await sleep(3)
        await ctx.send("What are you doing?")
        msg = await self.bot.wait_for("message", check = check)
        await ctx.trigger_typing()
        await sleep(3)
        await ctx.send("Sounds interesting")
    
    @commands.command(name="thanks", description="Thank me!")
    async def thanks(self, ctx):
        await ctx.send("Your welcome. 🙂")
    



def setup(bot):
    bot.add_cog(Conversation(bot))