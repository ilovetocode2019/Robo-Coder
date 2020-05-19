from discord.ext import commands
import discord
import os
import json
import asyncio
import pickle

class Moderation(commands.Cog):
    """Moderation commands to use on your server."""
    def __init__(self, bot):
        self.bot = bot
        self.open_channels = []
        if os.path.exists("logcha.json"):
            with open("logcha.json", "r") as f:
                self.bot.logging = json.load(f)
        else:
            with open("logcha.json", "w") as f:
                data = {}
                json.dump(data, f)
            self.bot.logging = {}

        if os.path.exists("channels.json"):
            with open("channels.json") as f:
                self.open_channels = json.load(f)
        else:
            with open("channels.json", "w") as f:
                self.open_channels = []
                json.dump(self.open_channels, f)

    def check(self, msg):
        if msg.author == self.bot.user or msg.author.id in [695463365400592476, 639607732202110977, 639234650782564362] or str(msg.guild.id) not in self.bot.logging:
            return False
        else:
            return True

    @commands.Cog.listener("on_message_delete")
    async def _deletion_detector(self, message):
        if not self.check(message):
            return
        chanid = self.bot.logging[str(message.guild.id)]
        channel = self.bot.get_channel(int(chanid))

        msg = "user: " + str(message.author) + "\nDeleted: " + str(message.content)
        title = "Deletion"
        em = discord.Embed(title = title, description = msg, color = 0x66FFCC)
        em.set_author(name = str(message.author.display_name), icon_url = message.author.avatar_url)
        em.set_footer(text = "Robo Coder")
        #await message.channel.send(embed=em)
        my_msg = await channel.send(embed = em)

    @commands.Cog.listener("on_message_edit")
    async def _edit_detector(self, before, after):
        if not self.check(before):
            return
        chanid = self.bot.logging[str(before.guild.id)]
        channel = self.bot.get_channel(int(chanid))

        #channel = self.bot.get_channel(699273282913959967)
        msg = "user: " + str(before.author) + "\nEdited: " + str(before.content) + "\nTo: " + str(after.content)
        title = "Edit"
        em = discord.Embed(title = title, description = msg, color = 0x66FFCC)
        em.set_author(name = str(before.author.display_name), icon_url = before.author.avatar_url)
        em.set_footer(text = "Robo Coder")
        #await message.channel.send(embed=em)
        my_msg = await channel.send(embed = em)

    @commands.command(name="setlog", description="Set a channel for logging")
    @commands.has_permissions(manage_guild=True)
    async def setlog(self, ctx):
        self.bot.logging[str(ctx.guild.id)] = str(ctx.channel.id)
        with open("logcha.json", "w") as f:
            json.dump(self.bot.logging, f)
        await ctx.send("Log set for this channel")

    @commands.command(name="unsetlog", description="Unset a channel for logging")
    @commands.has_permissions(manage_guild=True)
    async def unsetlog(self, ctx):
        if str(ctx.guild.id) not in self.bot.logging:
            return await ctx.send("Not enabled")
        self.bot.logging.pop(str(ctx.guild.id))
        with open("logcha.json", "w") as f:
            json.dump(self.bot.logging, f)
        await ctx.send("Log disabled for this channel")
    
    @commands.has_permissions(manage_guild=True)
    @commands.command(name="open", description="Open a temorary text channel", usage="(channel name)")
    async def open(self, ctx, channel_name="temporary-channel"):
        guild = ctx.guild
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if not existing_channel:
            new_channel = await guild.create_text_channel(channel_name)
            await ctx.send(f"Opened a chat: {channel_name}")
            self.open_channels.append(new_channel.id)
            with open("channels.json", "w") as f:
                json.dump(self.open_channels, f)

    @commands.has_permissions(manage_guild=True)
    @commands.command(name="close", description="Close a temorary text channel", usage="(channel name)")
    async def close(self, ctx, channel_name="temporary-channel"):
        search_channel = discord.utils.get(ctx.guild.text_channels, name = channel_name)
        if search_channel != None and search_channel.id in self.open_channels:
            await search_channel.delete()
            await ctx.send(f"Closed chat: {channel_name}")
            self.open_channels.remove(search_channel.id)
            with open("channels.json", "w") as f:
                json.dump(self.open_channels, f)

    @commands.command(name="openrn", description="Get a list of open chats")
    async def openchanns(self, ctx):
        channels = []
        for channel in self.open_channels:
            channels.append(self.bot.get_channel(channel).name)
        await ctx.send("\n".join(channels))

    @commands.command(name="")
def setup(bot):
    bot.add_cog(Moderation(bot))