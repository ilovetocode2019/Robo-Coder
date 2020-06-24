from discord.ext import commands
import discord
import asyncio

import random
import copy

class Chess:
    def __init__(self, ctx, msg, players):
        self.bot = ctx.bot
        self.ctx = ctx
        self.msg = msg
        self.players = players
        self.playercolors = {self.players[0]:"white", self.players[1]:"black"}
        self.turn = self.players[0]
        black = ChessPiece(None, "black", "⬛")
        white = ChessPiece(None, "white", "⬜")
        starter = [copy.deepcopy(black), copy.deepcopy(white), copy.deepcopy(black), copy.deepcopy(white), copy.deepcopy(black), copy.deepcopy(white), copy.deepcopy(black), copy.deepcopy(white)]
        self.board = {"A":[copy.deepcopy(Rook("white")), copy.deepcopy(Knight("white")), copy.deepcopy(Bishop("white")), copy.deepcopy(King("white")), copy.deepcopy(Queen("white")), copy.deepcopy(Bishop("white")), copy.deepcopy(Knight("white")), copy.deepcopy(Rook("white"))], "B":[copy.deepcopy(Pawn("white")) for x in range(8)], "C":starter, "D":[copy.deepcopy(x) for x in reversed(starter)], "E":copy.deepcopy(starter), "F":[copy.deepcopy(x) for x in reversed(starter)], "G":[copy.deepcopy(Pawn("black")) for x in range(8)], "H":[copy.deepcopy(Rook("black")), copy.deepcopy(Knight("black")), copy.deepcopy(Bishop("black")), copy.deepcopy(King("black")), copy.deepcopy(Queen("black")), copy.deepcopy(Bishop("black")), copy.deepcopy(Knight("black")), copy.deepcopy(Rook("black"))]}
        print(self.board)
    
    def embed(self):
        message = "⬛1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣"
        for row in copy.deepcopy(self.board):
            message += f"\n{row}{''.join([x.char for x in self.board[row]])}"
        message += f"\n{str(self.ctx.guild.get_member(self.turn))}'s turn"
        em = self.bot.build_embed(title="Chess", description=message)
        em.set_footer(text=f"{str(self.ctx.guild.get_member(self.players[0]))} vs {str(self.ctx.guild.get_member(self.players[1]))}")
        return em


class ChessPiece:
    def __init__(self, name, color, char):
        self.name = name
        self.color = color
        self.char = char

class King(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♕"
        else:
            char = "  ♛"

        super().__init__("King", color, char)

    def piece_check(self, location):
        return True, None

class Queen(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♔"
        else:
            char = "  ♚"
        super().__init__("Queen", color, char)

    def piece_check(self, location):
        return True, None

class Bishop(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♗"
        else:
            char = "  ♝"
        super().__init__("Bishop", color, char)

    def piece_check(self, location):
        return True, None

class Knight(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♖"
        else:
            char = "  ♜"
        super().__init__("Knight", color, char)

    def piece_check(self, location):
        return True, None

class Rook(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♘"
        else:
            char = "  ♞"
        super().__init__("Rook", color, char)

    def piece_check(self, location):
        return True, None

class Pawn(ChessPiece):
    def __init__(self, color):
        if color == "white":
            char = "  ♙"
        else:
            char = "  \♟"
        super().__init__("Pawn", color, char) 

    def piece_check(self, location):
        return True, None

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
        em = self.bot.build_embed(title="Tic Tac Toe", description="Tic Tac Toe game", color=discord.Colour.from_rgb(*self.bot.customization[str(self.ctx.guild.id)]["color"]))
        em.add_field(name="Board", value=str(board), inline=False)
        em.set_footer(text=" vs ".join([f'{str(x)} ({self.playericos[x]})' for x in self.players]))
        await self.msg.edit(content=None, embed=em)

    async def turn(self, user):
        reactionconvert = {"9\N{combining enclosing keycap}":8, "8\N{combining enclosing keycap}":7, "7\N{combining enclosing keycap}":6, "6\N{combining enclosing keycap}":5, "5\N{combining enclosing keycap}":4, "4\N{combining enclosing keycap}":3, "3\N{combining enclosing keycap}":2, "2\N{combining enclosing keycap}":1, "1\N{combining enclosing keycap}":0}
        await self.update("It's " + str(user) + "'s turn")
        def check(reaction, author):
            #Check if the user is correct
            return author == user and reaction.message.channel == self.ctx.channel and reaction.emoji in reactionconvert
        tasks = [
                                asyncio.ensure_future(self.bot.wait_for('reaction_add', check=check)),
                                asyncio.ensure_future(self.bot.wait_for('reaction_remove', check=check))
                ]
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
        
    @commands.guild_only()
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
        ctx.tttgame = TicTacToe(ctx, self.bot, msg, players)
        await ctx.tttgame.update(ctx.author)
        game = True
        while game:
            for user in ctx.tttgame.players:
                try:
                    await ctx.tttgame.turn(user)
                except asyncio.TimeoutError:
                    return await ctx.send("Tic Tac Toe has timed out")
                won = await ctx.tttgame.checkwin(user)
                if won == True:
                    await ctx.tttgame.update(str(user) + " won 🎉!")
                    game = False
                    break
                if await ctx.tttgame.checktie() == True:
                    await ctx.tttgame.update("The game was a tie")
                    game = False
                    break
    
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="hangman", description="A hangman game")
    async def hangman(self, ctx):
        pictures = {6:"https://upload.wikimedia.org/wikipedia/commons/8/8b/Hangman-0.png",
            5:"https://upload.wikimedia.org/wikipedia/commons/3/30/Hangman-1.png",
            4:"https://upload.wikimedia.org/wikipedia/commons/7/70/Hangman-2.png",
            3:"https://upload.wikimedia.org/wikipedia/commons/9/97/Hangman-3.png",
            2:"https://upload.wikimedia.org/wikipedia/commons/2/27/Hangman-4.png",
            1:"https://upload.wikimedia.org/wikipedia/commons/6/6b/Hangman-5.png",
            0:"https://upload.wikimedia.org/wikipedia/commons/d/d6/Hangman-6.png"}
        await ctx.send("Please configure a word in your DMs")
        await ctx.author.send("What is your word?")
        def check(msg):
            return msg.author == ctx.author and msg.channel.id == ctx.author.dm_channel.id
        message = await self.bot.wait_for("message", check=check)
        word = message.content.lower()
        lives = 6
        guessed = ""
        incorrect = []
        already_guessed = []
        for counter in range(len(word)):
            if word[counter] == " ":
                guessed += " "
            else:
                guessed += "\N{WHITE LARGE SQUARE}"
        em = self.bot.build_embed(title="Hangman", description="Click the hand reaction to make a guess")
        em.add_field(name="Tries Remaining", value=str(lives))
        if len(incorrect) != 0:
            em.add_field(name="Incorrect guesses", value=", ".join(incorrect))
        em.add_field(name="Guessing", value=guessed)
        em.set_thumbnail(url=pictures[lives])
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
            try:
                for task in pending:
                    task.cancel()

                    if len(done) == 0:
                        raise asyncio.TimeoutError()
            except asyncio.TimeoutError:
                return await ctx.send("Hangman has timed out")
            

            #Get the awnser
            reaction, reaction_user = done.pop().result()

            ask = await ctx.send(f"{str(reaction_user)}: What is your guess?")
            def check(msg):
                return msg.author.id == reaction_user.id and msg.channel == reaction.message.channel
            reply = await self.bot.wait_for("message", check=check)
            if len(reply.content) != 1:
                await ctx.send("That not a letter", delete_after=5)
            elif reply.content in already_guessed:
                await ctx.send("You already guessed that", delete_after=5)

            elif reply.content in word: 
                await ctx.send("Your guess was right", delete_after=5)
                counter = 0
                for letter in word:
                    if letter == reply.content:
                        guessed = guessed[:counter] + reply.content + guessed[counter+len(reply.content):]
                    counter += 1

                em = self.bot.build_embed(title="Hangman", description="Click the hand reaction to make a guess")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Guesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)

            else:
                incorrect.append(reply.content)
                lives -= 1
                incorrect_msg = await ctx.send("Your guess was incorrect", delete_after=5)
                em = self.bot.build_embed(title="Hangman", description="Click the hand reaaction to make a guess")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Guesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)

            already_guessed.append(reply.content)


            async def clearup(reply, ask):
                if ctx.guild.me.guild_permissions.manage_messages:
                    await asyncio.sleep(5)
                    await reply.delete()
                    await ask.delete()
            self.bot.loop.create_task(clearup(reply, ask))
            
            if word == guessed:
                em = self.bot.build_embed(title="Hangman", description="You won 🎉!")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Guesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)
                return await ctx.send("You won hangman!")

            if lives == 0:
                em = self.bot.build_embed(title="Hangman", description="You lost")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Gusesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)
                return await ctx.send(f"You lost hangman. The word was ||{word}||")
     
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="chess", description="A chess game", usage="[opponent]")
    async def chess(self, ctx, opponent: discord.Member):
        game_msg = await ctx.send("Setting up the game")
        await game_msg.add_reaction("✋")
        players = [ctx.author.id, opponent.id]
        random.shuffle(players)
        game = Chess(ctx, game_msg, players)

        await game.msg.edit(content=None, embed=game.embed())
        await game.msg.edit(content=None, embed=game.embed())
        while True:
            for player in game.players:
                game.turn = player
                await game_msg.edit(embed=game.embed())
                def check(reaction, user):
                    return reaction.message.id == game_msg.id and user.id == player and str(reaction.emoji) == "✋"

                tasks = [
                                        asyncio.ensure_future(self.bot.wait_for('reaction_add', check=check)),
                                        asyncio.ensure_future(self.bot.wait_for('reaction_remove', check=check))
                        ]
                done, pending = await asyncio.wait(tasks, timeout=600, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()

                    if len(done) == 0:
                        raise asyncio.TimeoutError()

                reaction, reaction_user = done.pop().result()
                
                sent_messages = []
                while True:
                  
                    sent_messages.append(await ctx.send("What is your move? (e.g., A1 - A2)"))
                    def check(msg):
                        return msg.author.id == reaction_user.id and msg.channel.id == reaction.message.channel.id and msg.author.id != self.bot.user.id
                    
                    while True:
                        try:
                            reply = await self.bot.wait_for("message", check=check)
                            sent_messages.append(reply)

                            selected, destination = reply.content.split(" - ")
                            break
                        except:
                            sent_messages.append(await ctx.send("Make sure to type you awnser in a format like: A1 - A2"))


                    selected_piece = game.board[selected[0]][int(selected[1])-1]

                    if selected_piece.color != game.playercolors[player]:
                        sent_messages.append(await ctx.send("That piece is not yours!"))

                    elif not selected_piece.name:
                        sent_messages.append(await ctx.send("There is no piece in that spot!"))

                    else:
                        game.board[destination[0]][int(destination[1])-1] = copy.deepcopy(selected_piece)
                         
                        if (selected[0] in ["A", "C", "E", "G"] and int(selected[1]) in [2, 4, 6, 8]) or (selected[0] in ["B", "D", "F", "H"] and int(selected[1]) in [1, 3, 5, 7]):
                            selected_piece.name = None
                            selected_piece.color = "white"
                            selected_piece.char = "⬜"
                        else:
                            selected_piece.name = None
                            selected_piece.color = "black"
                            selected_piece.char = "⬛"


                        sent_messages.append(await ctx.send("Chess move made"))
                        break

                if ctx.guild.me.guild_permissions.manage_messages:
                    for message in sent_messages:
                        await message.delete()


def setup(bot):
    bot.add_cog(Games(bot))