from discord.ext import commands
import discord
import asyncio
import pathlib
from datetime import datetime
from datetime import timezone

from .utils import custom
class Notes(commands.Cog):
    """Sticky notes and todo lists."""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def note(self, ctx):
        await ctx.send_help(self)

    @note.command(name="list", description="Check your sticky notes")
    async def notelist(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT id, title, Content FROM notes WHERE notes.Userid=$1", ctx.author.id)
        em = self.bot.build_embed(title="Sticky notes", color=custom.Color.notes)
        for row in rows:
            em.add_field(name=row[1], value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)

    @note.command(name="add", description="Add a note", usage="[title] [content]")
    async def noteadd(self, ctx, title, *, content):
        await self.bot.db.execute("INSERT INTO notes(Userid, Title, Content) VALUES ($1, $2, $3)", ctx.author.id, str(title), str(content))
        await ctx.send("Note created")

    @note.command(name="delete", description="Remove a note", usage="[id]", aliases=["remove"])
    async def noteremove(self, ctx, content: int):
        rows = await self.bot.db.fetch("SELECT * FROM notes WHERE notes.userid=$1 AND notes.id=$2", ctx.author.id, content)
        if len(rows) == 0:
            return await ctx.send("That note doesn't exist")
        await self.bot.db.execute("DELETE FROM notes WHERE notes.userid=$1 AND notes.id=$2", ctx.author.id, content)
        await ctx.send("Note removed")
        
     
    @commands.group(invoke_without_command=True, description="See your todo list")
    async def todo(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT id, content, Status FROM todo WHERE todo.Userid=$1", ctx.author.id)
        em = self.bot.build_embed(title="Todo", description="", color=custom.Color.notes)
        for row in rows:
            em.description += f"\n{row[2]}: {row[1]} `{row[0]}`"

        await ctx.send(embed=em)

    @todo.command(name="add", description="Add something to your todo list", usage="[todo]")
    async def todoadd(self, ctx, *, content):
        await self.bot.db.execute(f'''INSERT INTO todo(userid, content, status) VALUES ($1, $2, $3)''', ctx.author.id, str(content), "Not started")
        await ctx.send("Todo list updated")

    @todo.command(name="start", description="Start something in your todo list", usage="[id]")
    async def todostart(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM todo WHERE todo.Userid=$1 and todo.ID=$2", ctx.author.id, content)
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE todo SET Status='Started' WHERE todo.userid=$1 AND todo.id=$2", ctx.author.id, content)
        await ctx.send(f"`{content}` started")

    @todo.command(name="complete", description="Complete something in your todo list", usage="[id]")
    async def todocomplete(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM todo WHERE todo.userid=$1 and todo.id=$2", ctx.author.id, content)
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE todo SET Status='Complete' WHERE todo.userid=$1 and todo.id=$2", ctx.author.id, content)
        await ctx.send(f"`{content}` Complete")

    @todo.command(name="delete", description="Remove something from your todo list", usage="[id]", aliases=["remove"])
    async def todoremove(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM todo WHERE todo.userid=$1 AND Todo.id=$2", ctx.author.id, content)
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"DELETE FROM todo WHERE todo.userid=$1 AND Todo.id=$2", ctx.author.id, content)
        await ctx.send("Removed from list")


def setup(bot):
    bot.add_cog(Notes(bot))