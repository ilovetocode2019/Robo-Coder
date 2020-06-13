from discord.ext import commands
import discord
import asyncio
import pathlib
from datetime import datetime
from datetime import timezone

class Notes(commands.Cog):
    """Sticky notes and todo lists."""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def note(self, ctx):
        await ctx.send_help(self)

    @note.command(name="list", description="Check your sticky notes")
    async def notelist(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT ID, Title, Content FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}'")
        if isinstance(ctx.channel, discord.DMChannel):
            em = discord.Embed(title="Sticky Notes")
        else:
            em = discord.Embed(title="Sticky Notes", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        for row in rows:
            em.add_field(name=row[1], value=f"{row[2]} `{row[0]}`", inline=False)
        await ctx.send(embed=em)

    @note.command(name="add", description="Add a note", usage="[title] [content]")
    async def noteadd(self, ctx, title, *, content):
        rows = await self.bot.db.fetch(f"SELECT ID FROM Notes;")
        if len(rows) == 0:
            rows = [[0]]
        await self.bot.db.execute(f'''INSERT INTO Notes(ID, Userid, Title, Content) VALUES ($1, $2, $3, $4)''', rows[-1][0]+1, str(ctx.author.id), str(title), str(content))
        await ctx.send("Note created")

    @note.command(name="delete", description="Remove a note", usage="[id]", aliases=["remove"])
    async def noteremove(self, ctx, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}' and Notes.ID={content};")
        if len(rows) == 0:
            return await ctx.send("That note doesn't exist")
        await self.bot.db.execute(f"DELETE FROM Notes WHERE Notes.Userid='{str(ctx.author.id)}' and Notes.ID={content};")
        await ctx.send("Note removed")
        
     
    @commands.group(invoke_without_command=True, description="See your todo list")
    async def todo(self, ctx):
        rows = await self.bot.db.fetch(f"SELECT ID, Content, Status FROM Todo WHERE Todo.Userid='{ctx.author.id}'")
        if isinstance(ctx.channel, discord.DMChannel):
            em = discord.Embed(title="Todo", description="")
        else:
            em = discord.Embed(title="Todo", description="", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        for row in rows:
            em.description += f"\n{row[2]}: {row[1]} `{row[0]}`"

        await ctx.send(embed=em)

    @todo.command(name="add", description="Add something to your todo list", usage="[todo]")
    async def todoadd(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT ID FROM Todo;")
        if len(rows) == 0:
            rows = [[0]]
        
        await self.bot.db.execute(f'''INSERT INTO Todo(ID, Userid, Content, Status) VALUES ($1, $2, $3, $4)''', rows[-1][0]+1, str(ctx.author.id), str(content), "Not started")
        await ctx.send("Todo list updated")

    @todo.command(name="start", description="Start something in your todo list", usage="[id]")
    async def todostart(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Started' WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        await ctx.send(f"`{content}` started")

    @todo.command(name="complete", description="Complete something in your todo list", usage="[id]")
    async def todocomplete(self, ctx, *, content):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"UPDATE Todo SET Status='Complete' WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        await ctx.send(f"`{content}` Complete")

    @todo.command(name="delete", description="Remove something from your todo list", usage="[id]", aliases=["remove"])
    async def todoremove(self, ctx, *, content: int):
        rows = await self.bot.db.fetch(f"SELECT * FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        if len(rows) == 0:
            return await ctx.send("That is not on your todo list")
        await self.bot.db.execute(f"DELETE FROM Todo WHERE Todo.Userid='{ctx.author.id}' and Todo.ID='{content}';")
        await ctx.send("Removed from list")


def setup(bot):
    bot.add_cog(Notes(bot))