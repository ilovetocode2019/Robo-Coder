from discord.ext import commands
import discord
import asyncio
import random

                
class TicTacToe:
    def __init__(self, ctx, bot, msg, players):
        self.ctx = ctx
        self.bot = bot
        self.msg = msg
        self.board = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:"]
        self.players = players
        self.playericos = {self.players[0]:":x:", self.players[1]:":o:"}
    
    async def update(self, bottom):
        board = f"{self.board[0]}{self.board[1]}{self.board[2]}\n{self.board[3]}{self.board[4]}{self.board[5]}\n{self.board[6]}{self.board[7]}{self.board[8]}\n{bottom}"
        em = discord.Embed(title="Tic Tac Toe", description="Tic Tac Toe game", color=0x008080)
        em.add_field(name="Board", value=str(board), inline=False)
        await self.msg.edit(content=None, embed=em)

    async def turn(self, user):
        reactionconvert = {"9\N{combining enclosing keycap}":8, "8\N{combining enclosing keycap}":7, "7\N{combining enclosing keycap}":6, "6\N{combining enclosing keycap}":5, "5\N{combining enclosing keycap}":4, "4\N{combining enclosing keycap}":3, "3\N{combining enclosing keycap}":2, "2\N{combining enclosing keycap}":1, "1\N{combining enclosing keycap}":0}
        await self.update("It's " + str(user) + "'s turn")
        def check(reaction, author):
            #Check if the user is correct
            return author == user and reaction.message.channel == self.ctx.channel and self.board[reactionconvert[reaction.emoji]] not in [":x:" or ":o:"]
        tasks = [
                                asyncio.ensure_future(self.bot.wait_for('reaction_add', check=check)),
                                asyncio.ensure_future(self.bot.wait_for('reaction_remove', check=check))
                ]
        try:
            #Wait for a reaction
            done, pending = await asyncio.wait(tasks, timeout=180, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

                if len(done) == 0:
                    raise asyncio.TimeoutError()

            #Get the awnser
            reaction, reaction_user = done.pop().result()
            self.board[reactionconvert[str(reaction.emoji)]] = self.playericos[user]
            await self.update("It's " + str(user) + "'s turn")
        except asyncio.TimeoutError:
            #This is what happens if the program times out
            raise Exception("The tic tac toe game has timed out")

    async def checkwin(self, user):
        win_commbinations = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]
        count = 0
        for a in win_commbinations:
                if self.board[a[0]] == self.board[a[1]] == self.board[a[2]] == self.playericos[user]:
                    return True

    async def checktie(self):
        placed = [":x:", ":o:"]
        if self.board[0] in placed and self.board[1] in placed and self.board[2] in placed and self.board[3] in placed and self.board[4] in placed and self.board[5] in placed and self.board[6] in placed and self.board[7] in placed and self.board[8] in placed:
            return True


class Games(commands.Cog):
    """Some fun games"""
    def __init__(self, bot):
        self.bot = bot
        self.tttgames = {}
    
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="tictactoe", description="A tic tac toe game", aliases=["ttt"], usage="[opponent]")
    async def ttt(self, ctx, *, opponent: discord.Member):
        msg = await ctx.send("Setting up the game....")
        await msg.add_reaction("1\N{combining enclosing keycap}")
        await msg.add_reaction("2\N{combining enclosing keycap}")
        await msg.add_reaction("3\N{combining enclosing keycap}")
        await msg.add_reaction("4\N{combining enclosing keycap}")
        await msg.add_reaction("5\N{combining enclosing keycap}")
        await msg.add_reaction("6\N{combining enclosing keycap}")
        await msg.add_reaction("7\N{combining enclosing keycap}")
        await msg.add_reaction("8\N{combining enclosing keycap}")
        await msg.add_reaction("9\N{combining enclosing keycap}")
        self.tttgames[ctx.guild.id] = TicTacToe(ctx, self.bot, msg, [ctx.author, opponent])
        await self.tttgames[ctx.guild.id].update(ctx.author)
        game = True
        while game:
            for user in self.tttgames[ctx.guild.id].players:
                await self.tttgames[ctx.guild.id].turn(user)
                won = await self.tttgames[ctx.guild.id].checkwin(user)
                if won == True:
                    await self.tttgames[ctx.guild.id].update(str(user) + " won 🎉!")
                    game = False
                    break
                if await self.tttgames[ctx.guild.id].checktie() == True:
                    await self.tttgames[ctx.guild.id].update("The game was a tie")
                    game = False
                    break
                

def setup(bot):
    bot.add_cog(Games(bot))