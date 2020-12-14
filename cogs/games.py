import discord
from discord.ext import commands

import asyncio
import random

class Hangman:
    def __init__(self, ctx, word):
        self.word = word
        self.incorrect = []
        self.correct = []
        self.bot = ctx.bot
        self.owner = ctx.author

    @property
    def guessed(self):
        word = ""
        for letter in self.word:
            if letter in self.correct:
                word += letter
            else:
                word += "_"
        return word

    @property
    def won(self):
        if self.word == self.guessed:
            return True
        elif 10-len(self.incorrect) == 0:
            return False
        else:
            return None

    @property
    def embed(self):
        em = discord.Embed(title="Hangman", color=0x96c8da)
        if self.guessed:
            em.add_field(name="Word", value=discord.utils.escape_markdown(self.guessed.replace("", " ")))

        if self.won:
            em.description = ":tada: You Won!"
        elif self.won == False:
            em.description = f"You Lost. The word was ||{self.word}||"

        if self.incorrect:
            em.add_field(name="Incorrect Guesses", value=", ".join(self.incorrect))
            em.add_field(name="Guess Remaining", value=10-len(self.incorrect))
        return em

class TicTacToe:
    def __init__(self, ctx, players):
        self.bot = ctx.bot
        self.ctx = ctx
        self.players = players
        self.turn = players[0]
        self.next = players[1]
        self.board = [None, None, None, None, None, None, None, None, None]

    @property
    def winner(self):
        for x in [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]:
                if self.board[x[0]] == self.board[x[1]] == self.board[x[2]] == True:
                    return self.players[0]

                if self.board[x[0]] == self.board[x[1]] == self.board[x[2]] == False:
                    return self.players[1]

    @property
    def tie(self):
        tie = True
        for piece in self.board:
            if piece == None:
                tie = False
        return tie

    @property
    def board_string(self):
        board = ""
        for counter, piece in enumerate(self.board):
            if counter%3 == 0:
                board += "\n"

            if piece:
                board += ":x:"
            elif piece == False:
                board += ":o:"
            else:
                numbers = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
                board += f":{numbers[counter+1]}:"
        return board

    @property
    def embed(self):
        if self.winner:
            message = f":tada: {self.winner} won!"
        elif self.tie:
            message = "Game was a tie"
        else:
            message = f"It is {self.turn}'s turn"

        em = discord.Embed(title="Tic Tac Toe", description=f"{self.board_string}\n\n{message}", color=0x96c8da)
        em.set_footer(text=f"{self.players[0]} (\N{CROSS MARK}) vs {self.players[1]} (\N{HEAVY LARGE CIRCLE})")
        return em

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":video_game:"
        self.hangman_games = {}
        self.tic_tac_toe_games = {}

    @commands.group(name="hangman", description="Play hangman in Discord", invoke_without_command=True)
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def hangman(self, ctx):
        if ctx.channel.id in self.hangman_games:
            return await ctx.send(":x: A hangman game is already running in this channel")

        try:
            await ctx.author.send("What is your hangman word?")
        except discord.Forbidden:
            return await ctx.send(":x: You need to have DMs enabled")

        try:
            msg = await self.bot.wait_for("message", check=lambda message: message.channel == ctx.author.dm_channel and message.author.id == ctx.author.id, timeout=180)
            word = msg.content
        except asyncio.TimeoutError:
            return await ctx.send(":x: Hangman creation timed out")

        if not word.isalpha():
            return await ctx.author.send(":x: That is not a valid word")

        self.hangman_games[ctx.channel.id] = hangman = Hangman(ctx, word)
        self.hangman_games[ctx.channel.id].message = await ctx.send(embed=self.hangman_games[ctx.channel.id].embed)

    @hangman.command(name="guess", description="Guess a word in a hangman game", aliases=["g"])
    async def hangman_guess(self, ctx, letter):
        hangman = self.hangman_games.get(ctx.channel.id)
        if not hangman:
            return await ctx.send(":x: No hangman game in this channel")
        if hangman.owner == ctx.author:
            return await ctx.send(":x: You cannot guess in your own game")

        if len(letter) != 1 or letter in hangman.correct + hangman.incorrect:
            await ctx.message.add_reaction("\N{HEAVY EXCLAMATION MARK SYMBOL}")
        elif letter in hangman.word:
            hangman.correct.append(letter)
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            hangman.incorrect.append(letter)
            await ctx.message.add_reaction("\N{CROSS MARK}")
        await hangman.message.edit(embed=hangman.embed)

        if hangman.won in (True, False):
            self.hangman_games.pop(ctx.channel.id)

    @hangman.command(name="stop", description="Stop the hangman game")
    async def hangman_stop(self, ctx):
        hangman = self.hangman_games.get(ctx.channel.id)
        if not hangman:
            return await ctx.send(":x: No hangman game is running this channel")
        if hangman.owner.id != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(":x: You do not own the hangman game")

        self.hangman_games.pop(ctx.channel.id)
        await ctx.send(":white_check_mark: Hangman game stopped")

    @commands.command(name="tictactoe", description="Play a tic tac toe", aliases=["ttt"])
    async def ttt(self, ctx, *, opponent: discord.Member):
        players = [ctx.author, opponent]
        random.shuffle(players)
        game = TicTacToe(ctx, players)
        game.message = await ctx.send(embed=game.embed)

        def check(reaction, user):
            return user == game.turn and reaction.message.id == game.message.id and str(reaction.emoji) in emojis

        emojis = {"1\N{combining enclosing keycap}": 1, "2\N{combining enclosing keycap}": 2, "3\N{combining enclosing keycap}": 3,
                    "4\N{combining enclosing keycap}": 4, "5\N{combining enclosing keycap}": 5, "6\N{combining enclosing keycap}": 6,
                    "7\N{combining enclosing keycap}": 7, "8\N{combining enclosing keycap}": 8, "9\N{combining enclosing keycap}": 9
        }
        for emoji in emojis:
            await game.message.add_reaction(emoji)

        while True:
            while True:
                reaction, user = await self.bot.wait_for("reaction_add", check=check)

                index = emojis[str(reaction.emoji)]
                if game.players[0] == game.turn:
                    icon = True
                else:
                    icon = False

                if game.board[index-1] == None:
                    game.board[index-1] = icon
                    game.turn, game.next = game.next, game.turn
                    break

            await game.message.edit(embed=game.embed)
            if game.winner or game.tie:
                break

def setup(bot):
    bot.add_cog(Games(bot))
