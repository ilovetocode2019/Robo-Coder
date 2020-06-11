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
        self.playericos = {self.players[0]:"\N{CROSS MARK}", self.players[1]:"\N{HEAVY LARGE CIRCLE}"}
    
    async def update(self, bottom):
        board = f"{self.board[0]}{self.board[1]}{self.board[2]}\n{self.board[3]}{self.board[4]}{self.board[5]}\n{self.board[6]}{self.board[7]}{self.board[8]}\n{bottom}"
        em = discord.Embed(title="Tic Tac Toe", description="Tic Tac Toe game", color=discord.Colour.from_rgb(*self.bot.customization[str(self.ctx.guild.id)]["color"]))
        em.add_field(name="Board", value=str(board), inline=False)
        em.set_footer(text=" vs ".join([f'{str(x)} ({self.playericos[x]})' for x in self.players]))
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
        placed = ["\N{CROSS MARK}", "\N{HEAVY LARGE CIRCLE}"]
        if self.board[0] in placed and self.board[1] in placed and self.board[2] in placed and self.board[3] in placed and self.board[4] in placed and self.board[5] in placed and self.board[6] in placed and self.board[7] in placed and self.board[8] in placed:
            return True

class GameTimedOut(Exception):
    pass

class Games(commands.Cog):
    """Fun games."""
    def __init__(self, bot):
        self.bot = bot
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
        players = [ctx.author, opponent]
        random.shuffle(players)
        tttgame = TicTacToe(ctx, self.bot, msg, players)
        await tttgame.update(ctx.author)
        game = True
        while game:
            for user in tttgame.players:
                await tttgame.turn(user)
                won = await tttgame.checkwin(user)
                if won == True:
                    await tttgame.update(str(user) + " won 🎉!")
                    game = False
                    break
                if await tttgame.checktie() == True:
                    await tttgame.update("The game was a tie")
                    game = False
                    break

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="hangman", description="A hangman game")
    async def hangman(self, ctx):
        await ctx.send("Please configure a word in your DMs")
        await ctx.author.send("What is your word?")
        def check(msg):
            return msg.author == ctx.author and msg.channel.id == ctx.author.dm_channel.id
        message = await self.bot.wait_for("message", check=check)
        word = message.content.lower()
        lives = 10
        guessed = ""
        incorrect = []
        for counter in range(len(word)):
            if word[counter] == " ":
                guessed += " "
            else:
                guessed += "\N{WHITE LARGE SQUARE}"
        em = discord.Embed(title="Hangman", description="Hangman game", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
        em.add_field(name="Tries remaining", value=str(lives))
        if len(incorrect) != 0:
            em.add_field(name="Already Guessed", value=", ".join(incorrect))
        em.add_field(name="Guessing", value=guessed)
        em.add_field(name="Status", value="Playing")
        game_msg = await ctx.send(embed=em)
        await game_msg.add_reaction("✋")
        while True:
            def check(reaction, user):
                return reaction.message.id == game_msg.id and user.id != self.bot.user.id and str(reaction.emoji) == "✋"
            tasks = [
                                    asyncio.ensure_future(self.bot.wait_for('reaction_add', check=check)),
                                    asyncio.ensure_future(self.bot.wait_for('reaction_remove', check=check))
                    ]
            done, pending = await asyncio.wait(tasks, timeout=180, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

                if len(done) == 0:
                    raise asyncio.TimeoutError()

            #Get the awnser
            reaction, reaction_user = done.pop().result()

            ask = await ctx.send(f"{str(reaction_user)}: What is your guess?")
            def check(msg):
                return msg.author.id == reaction_user.id and msg.channel == reaction.message.channel
            reply = await self.bot.wait_for("message", check=check)
            if len(reply.content) != 1:
                await ctx.send("That not a letter", delete_after=5)
            elif reply.content in word:
                await ctx.send("Your guess was right", delete_after=5)
                counter = 0
                for letter in word:
                    if letter == reply.content:
                        guessed = guessed[:counter] + reply.content + guessed[counter+len(reply.content):]
                    counter += 1

                em = discord.Embed(title="Hangman", description="Hangman game", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
                em.add_field(name="Tries remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Already Guessed", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.add_field(name="Status", value="Playing")
                await game_msg.edit(embed=em)

            else:
                incorrect.append(reply.content)
                lives -= 1
                incorrect_msg = await ctx.send("Your guess was incorrect", delete_after=5)
                em = discord.Embed(title="Hangman", description="Hangman game", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
                em.add_field(name="Tries remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Already Guessed", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.add_field(name="Status", value="Playing")
                await game_msg.edit(embed=em)


            async def clearup(reply, ask):
                if ctx.guild.me.guild_permissions.manage_messages:
                    await asyncio.sleep(5)
                    await reply.delete()
                    await ask.delete()
            self.bot.loop.create_task(clearup(reply, ask))
            
            if word == guessed:
                em = discord.Embed(title="Hangman", description="Hangman game", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
                em.add_field(name="Tries remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Already Guessed", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.add_field(name="Status", value="Won 🎉!")
                await game_msg.edit(embed=em)
                return await ctx.send("You won hangman!")

            if lives == 0:
                em = discord.Embed(title="Hangman", description="Hangman game", color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
                em.add_field(name="Tries remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Already Guessed", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.add_field(name="Status", value="Lost")
                await game_msg.edit(embed=em)
                return await ctx.send(f"You lost hangman. The word was ||{word}||")


                

def setup(bot):
    bot.add_cog(Games(bot))