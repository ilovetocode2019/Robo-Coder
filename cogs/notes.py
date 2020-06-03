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
    async def notelist(self, ctx):
        cursor = await self.bot.db.execute(f"SELECT Title, Content FROM Notes WHERE Notes.ID='{str(ctx.author.id)}'")
        rows = await cursor.fetchall()
        em = discord.Embed(title="Sticky Notes", color=0X00ff00)
        for row in rows:
            em.add_field(name=row[0], value=row[1], inline=False)
        await ctx.send(embed=em)
        await cursor.close()

    @note.command(name="add", description="Add a note", usage="[title] [content]")
    async def noteadd(self, ctx, title, *, content):
        await self.bot.db.execute(f"INSERT INTO Notes('ID', 'Title', 'Content') VALUES ('{str(ctx.author.id)}', '{title}', '{content}');")
        await self.bot.db.commit()
        await ctx.send("Note created")

    @note.command(name="remove", description="Remove a note", usage="[title]")
    async def noteremove(self, ctx, title):
        cursor = await self.bot.db.execute(f"SELECT * FROM Notes WHERE Notes.ID='{str(ctx.author.id)}' and Notes.title='{title}';")
        if len(await cursor.fetchall()) == 0:
            return await ctx.send("That note doesn't exist")
        await self.bot.db.execute(f"DELETE FROM Notes WHERE Notes.ID='{str(ctx.author.id)}' and Notes.Title='{title}';")
        await self.bot.db.commit()
        await ctx.send("Note deleted")
     
    @commands.group(invoke_without_command=True, description="See your todo list")
    async def todo(self, ctx):
        cursor = await self.bot.db.execute(f"SELECT Content, Status FROM Todo WHERE Todo.UseriD='{ctx.author.id}'")
        rows = await cursor.fetchall()
        await cursor.close()
        em = discord.Embed(title="Todo", description="", color=0X00ff00)
        for row in rows:
            em.description += f"\n{row[1]}: {row[0]}"

        await ctx.send(embed=em)

    @todo.command(name="add", description="Add something to your todo list", usage="[todo]")
    async def todoadd(self, ctx, *, content):
        await self.bot.db.execute(f"INSERT INTO Todo('Userid', 'Content', 'Status') VALUES ('{ctx.author.id}', '{content}', 'Not started');")
        await self.bot.db.commit()
        await ctx.send("Todo list updated")

    @todo.command(name="start", description="Start something in your todo list", usage="[todo]")
    async def todostart(self, ctx, *, content):
        cursor = await self.bot.db.execute(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(await cursor.fetchall()) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Started' WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await self.bot.db.commit()
        await ctx.send(f"`{content}` started")

    @todo.command(name="complete", description="Complete something in your todo list", usage="[todo]")
    async def todocomplete(self, ctx, *, content):
        cursor = await self.bot.db.execute(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(await cursor.fetchall()) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Complete' WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await self.bot.db.commit()
        await ctx.send(f"`{content}` Complete")

    @todo.command(name="remove", description="Remove something from your todo list")
    async def todoremove(self, ctx, *, content):
        cursor = await self.bot.db.execute(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(await cursor.fetchall()) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"DELETE FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await self.bot.db.commit()
        await ctx.send("Removed from list")


def setup(bot):
    bot.add_cog(Notes(bot))