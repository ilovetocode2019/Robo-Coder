from discord.ext import commands
import discord
import os
import json
import asyncio
import pickle

class Moderation(commands.Cog):
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
        if msg.author == self.bot.user or msg.author.bot or str(msg.guild.id) not in self.bot.logging:
            return False
        else:
            return True
    
    @commands.Cog.listener("on_member_update")
    async def _on_member_update(self, before, after):
        if not str(before.guild.id) in self.bot.logging or before.bot or before.nick == after.nick:
            return False
            
        chanid = self.bot.logging[str(before.guild.id)]
        channel = self.bot.get_channel(int(chanid))

        em = discord.Embed(title="Nickname update", value=str(before.name), color=discord.Colour.blue())
        em.add_field(name="Before", value=str(before.nick))
        em.add_field(name="Affter", value=str(after.nick))
        em.set_footer(text=self.bot.user.name)
        await channel.send(embed=em)

    @commands.Cog.listener("on_message_delete")
    async def _deletion_detector(self, message):
        if not self.check(message):
            return
        chanid = self.bot.logging[str(message.guild.id)]
        channel = self.bot.get_channel(int(chanid))

        msg = "user: " + str(message.author) + "\nDeleted: " + str(message.content)
        title = "Deletion"
        em = discord.Embed(title=title, description=msg, color=discord.Colour.red())
        em.set_author(name = str(message.author.display_name), icon_url = message.author.avatar_url)
        em.set_footer(text=self.bot.user.name)
        my_msg = await channel.send(embed = em)

    @commands.Cog.listener("on_message_edit")
    async def _edit_detector(self, before, after):
        if not self.check(before):
            return
        chanid = self.bot.logging[str(before.guild.id)]
        channel = self.bot.get_channel(int(chanid))

        msg = "user: " + str(before.author) + "\nEdited: " + str(before.content) + "\nTo: " + str(after.content)
        title = "Edit"
        em = discord.Embed(title = title, description = msg, color=discord.Colour.blue())
        em.set_author(name = str(before.author.display_name), icon_url = before.author.avatar_url)
        em.add_field(name="Jump!", value=f"https://discord.com/channels/{after.guild.id}/{after.channel.id}/{after.id}")
        em.set_footer(text=self.bot.user.name)
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

    @commands.command(name="kick", description="Kick a member from the server", usage="[user]")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, *, member:discord.Member):
        await member.kick()
        await ctx.send(f"{member.name} kicked")

    @commands.command(name="ban", description="Ban a member from the server", usage="[user]")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, *, member:discord.Member):
        await member.ban()
        await ctx.send(f"{member.name} banned")

    @commands.command(name="purge", description="Delete a mass amount of messages", usage="[amount]", hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, *, arg):
        await ctx.send("Deleting " + str(arg) + " messages......")
        await asyncio.sleep(4)
        await ctx.channel.purge(limit=int(arg)+1)

        
def setup(bot):
    bot.add_cog(Moderation(bot))