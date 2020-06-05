from discord.ext import commands
import discord
import asyncio
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
        rows = await self.bot.db.fetch(f"SELECT Title, Content FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}'")
        em = discord.Embed(title="Sticky Notes", color=0X00ff00)
        for row in rows:
            em.add_field(name=row[0], value=row[1], inline=False)
        await ctx.send(embed=em)

    @note.command(name="add", description="Add a note", usage="[title] [content]")
    async def noteadd(self, ctx, title, *, content):
        await self.bot.db.execute(f'''INSERT INTO Notes(Userid, Title, Content) VALUES ($1, $2, $3)''', str(ctx.author.id), str(title), str(content))
        await ctx.send("Note created")

    @note.command(name="remove", description="Remove a note", usage="[title]")
    async def noteremove(self, ctx, title):
        rows = await self.bot.db.fetch(f"SELECT * FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}' and Notes.title='{title}';")
        if len(rows) == 0:
            return await ctx.send("That note doesn't exist")
        await self.bot.db.execute(f"DELETE FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}' and Notes.Title='{title}';")
        await ctx.send("Note deleted")
     
    @commands.group(invoke_without_command=True, description="See your todo list")
    async def todo(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT Content, Status FROM Todo WHERE Todo.Userid='{ctx.author.id}'")
        em = discord.Embed(title="Todo", description="", color=0X00ff00)
        for row in rows:
            em.description += f"\n{row[1]}: {row[0]}"

        await ctx.send(embed=em)

    @todo.command(name="add", description="Add something to your todo list", usage="[todo]")
    async def todoadd(self, ctx, *, content):
        await self.bot.db.execute(f'''INSERT INTO Todo(Userid, Content, Status) VALUES ($1, $2, $3)''', str(ctx.author.id), str(content), "Not started")
        await ctx.send("Todo list updated")

    @todo.command(name="start", description="Start something in your todo list", usage="[todo]")
    async def todostart(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Started' WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await ctx.send(f"`{content}` started")

    @todo.command(name="complete", description="Complete something in your todo list", usage="[todo]")
    async def todocomplete(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Complete' WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await ctx.send(f"`{content}` Complete")

    @todo.command(name="remove", description="Remove something from your todo list")
    async def todoremove(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"DELETE FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.content='{content}';")
        await ctx.send("Removed from list")


def setup(bot):
    bot.add_cog(Notes(bot))