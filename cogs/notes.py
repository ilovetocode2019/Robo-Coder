from discord.ext import commands
import discord
import asyncio
import aiosqlite
import pathlib
from datetime import datetime
from datetime import timezone

class Notes(commands.Cog):
    """Keep sticky notes and read them at any time."""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def note(self, ctx):
        await ctx.send("Use 'r!help note' to get help on sticky notes")

    @note.command(name="list", description="Check your sticky notes")
    async def todolist(self, ctx):
        cursor = await self.bot.db.execute(f"SELECT Title, Content FROM Notes WHERE Notes.ID='{str(ctx.author.id)}'")
        rows = await cursor.fetchall()
        em = discord.Embed(title="Stick Notes", color=0X00ff00)
        for row in rows:
            em.add_field(name=row[0], value=row[1], inline=False)
        await ctx.send(embed=em)
        await cursor.close()

    @note.command(name="add", description="Add a note", usage="'[title]' '[content]'")
    async def noteadd(self, ctx, title, content):
        await self.bot.db.execute(f"INSERT INTO Notes('ID', 'Title', 'Content') VALUES ('{str(ctx.author.id)}', '{title}', '{content}');")
        await self.bot.db.commit()
        await ctx.send("Note created")

    @note.command(name="remove", description="Remove a note", usage="'[title]'")
    async def noteremove(self, ctx, title):
        await self.bot.db.execute(f"DELETE FROM Notes WHERE Notes.ID='{str(ctx.author.id)}' and Notes.Title='{title}';")
        await self.bot.db.commit()
        await ctx.send("Note deleted")

    @commands.command("allnotes", description="Veiw all the notes in the database", hidden=True)
    @commands.is_owner()
    async def notes(self, ctx):
        cursor = await self.bot.db.execute('SELECT * FROM Notes')
        row = await cursor.fetchall()
        await ctx.send(str(row))
        await cursor.close()

    """@commands.command(name="getlink", description="Get a to a message")
    async def getlink(self, ctx):
        msg = await ctx.send("Linked message")
        if isinstance(ctx.channel, discord.channel.DMChannel):
            link = f"https://discordapp.com/channels/@me/{ctx.author.dm_channel.id}/{msg.id}"
        else:
            link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{msg.id}"
        await ctx.send(link)

    @commands.command(name="time")
    async def time(self, ctx):
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%M")
        day = now.strftime("%d")
        time = now.strftime("%H:")
        minute = now.strftime("%M:")

        timestamp = now.replace(tzinfo=timezone.utc).timestamp()
        await ctx.send(str(timestamp))"""
def setup(bot):
    bot.add_cog(Notes(bot))