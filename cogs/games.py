from discord.ext import commands
import discord
import asyncio

import random
import copy

from .utils import uno
import time

import importlib
import traceback


class TicTacToe:
    """Represents a tic tac toe game"""

    def __init__(self, ctx, bot, msg, players):
        self.ctx = ctx
        self.bot = bot
        self.msg = msg
        self.board = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:"]
        self.players = players
        self.playericos = {self.players[0]:"\N{CROSS MARK}", self.players[1]:"\N{HEAVY LARGE CIRCLE}"}
    
    async def update(self, bottom):
        """Returns a discord.Embed with a specified bottom"""

        board = f"{self.board[0]}{self.board[1]}{self.board[2]}\n{self.board[3]}{self.board[4]}{self.board[5]}\n{self.board[6]}{self.board[7]}{self.board[8]}\n{bottom}"
        em = self.bot.build_embed(title="Tic Tac Toe", description="Tic Tac Toe game")
        em.add_field(name="Board", value=str(board), inline=False)
        em.set_footer(text=" vs ".join([f'{str(x)} ({self.playericos[x]})' for x in self.players]))
        await self.msg.edit(content=None, embed=em)

    async def turn(self, user):
        """Runs a turn"""

        reactionconvert = {"9\N{combining enclosing keycap}":8, "8\N{combining enclosing keycap}":7, "7\N{combining enclosing keycap}":6, "6\N{combining enclosing keycap}":5, "5\N{combining enclosing keycap}":4, "4\N{combining enclosing keycap}":3, "3\N{combining enclosing keycap}":2, "2\N{combining enclosing keycap}":1, "1\N{combining enclosing keycap}":0}
        await self.update("It's " + str(user) + "'s turn")
        def check(reaction, author):
            #Check if it's the reaction we are looking for
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

        #Make the move and update the board embed
        reaction, reaction_user = done.pop().result()
        self.board[reactionconvert[str(reaction.emoji)]] = self.playericos[user]
        await self.update("It's " + str(user) + "'s turn")

    async def checkwin(self, user):
        """Checks if someone has one the game"""

        win_commbinations = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]
        count = 0
        for a in win_commbinations:
                if self.board[a[0]] == self.board[a[1]] == self.board[a[2]] == self.playericos[user]:
                    return True

    async def checktie(self):
        """Checks if the game was a tie"""

        placed = ["\N{CROSS MARK}", "\N{HEAVY LARGE CIRCLE}"]
        if self.board[0] in placed and self.board[1] in placed and self.board[2] in placed and self.board[3] in placed and self.board[4] in placed and self.board[5] in placed and self.board[6] in placed and self.board[7] in placed and self.board[8] in placed:
            return True

class GameTimedOut(Exception):
    pass

class Games(commands.Cog):
    """Fun games."""
    def __init__(self, bot):
        self.bot = bot
        self.uno_games = {}

    async def wait_for_reaction_update(self, ctx, msg):
        """Used in the uno game, wait's for a reaction update to add a new player"""

        def check(reaction, user):
            if not reaction.message.guild:
                return False
            return reaction.message.guild.id == ctx.guild.id and reaction.message.id == msg.id and str(reaction.emoji) == "✅" and user.id != self.bot.user.id

        tasks = [
                asyncio.ensure_future(self.bot.wait_for('reaction_add', check=check)),
                asyncio.ensure_future(self.bot.wait_for('reaction_remove', check=check))
                ]
    
        done, pending = await asyncio.wait(tasks, timeout=20, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

            if len(done) == 0:
                raise asyncio.TimeoutError()

        return done.pop().result()
    
    @commands.guild_only()
    @commands.cooldown(1, 600, commands.BucketType.guild)
    @commands.group(name="uno", description="Start a uno game", invoke_without_command=True)
    async def uno_command(self, ctx):
        #Run the uno game checks
        if ctx.guild.id in self.uno_games:
            return await ctx.send("❌ A uno game in this server is already happening")

        if not ctx.guild.me.guild_permissions.manage_channels:
            await ctx.send("❌ I need manage channels to do uno")
            return
        if not ctx.guild.me.guild_permissions.manage_messages:
            await ctx.send("❌ I need manage messages to do uno")
            return
        
        #Create a game
        ctx.game = uno.Game(ctx)
        self.uno_games[ctx.guild.id] = ctx.game
        await asyncio.sleep(3)
        await ctx.game.add_player(ctx.author)
        em = self.bot.build_embed(title="Uno", description="Click the check to join")
        em.add_field(name="Players", value="\n".join([player.mention for player in ctx.game.players]))
        msg = await ctx.send(embed=em)
        await msg.add_reaction("✅")
        counter = time.time()
        
        #Wait for players, stop waiting if it times out
        while True:
            try:
                reaction, user = await self.wait_for_reaction_update(ctx, msg)
            except asyncio.TimeoutError:
                break

            if user in ctx.game.players:
                ctx.game.players.remove(user)
                try:
                    await ctx.game.channels[user].delete()
                except:
                    pass
            else:
                await ctx.game.add_player(user)
            
            em = self.bot.build_embed(title="Uno", description="Click the check to join")
            em.add_field(name="Players", value="\n".join([player.mention for player in ctx.game.players]) or "No players")
            await msg.edit(embed=em)
            
            if time.time()-counter > 19:
                break
        
        #Run and reuturn if not enough players
        if len(ctx.game.players) < 2:
            em = self.bot.build_embed(title="Uno", description="Sorry, not enough players joined the game")
            em.add_field(name="Players", value="\n".join([player.mention for player in ctx.game.players]) or "No players")
            await msg.edit(embed=em)
            await ctx.game.cleanup()
            self.uno_games.pop(ctx.guild.id)
            return


        em = self.bot.build_embed(title="Uno", description="The game has started")
        em.add_field(name="Players", value="\n".join([player.mention for player in ctx.game.players]) or "No players")

        await msg.edit(embed=em)
        
        #Creates a task and wait for the uno game to complete, then delete it from the dict
        await ctx.game.start_game()
        await ctx.game.game_finished.wait()
        self.uno_games.pop(ctx.guild.id)
    
    @commands.guild_only()
    @uno_command.command(name="stop", description="Stop the uno game")
    async def uno_stop(self, ctx):
        #Check to make sure that the uno game is real, and they own it
        if ctx.guild.id not in self.uno_games:
            return await ctx.send("❌ No uno game for guild")
        
        ctx.game = self.uno_games[ctx.guild.id]

        if ctx.game.owner.id != ctx.author.id:
            return await ctx.send("❌ You do not own this game")
        
        #Cleanup the game
        ctx.game.main_loop.cancel()
        ctx.game.game_finished.set()
        await ctx.game.cleanup()
        await ctx.send("Game has been stopped")

    @commands.command(name="reload_uno", description="Reload uno.utils", hidden=True)
    @commands.is_owner()
    async def reload_uno(self, ctx):
        importlib.reload(uno)
        await ctx.send("**🔁 Reloaded** `cogs.utils.uno`")

    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="tictactoe", description="A tic tac toe game", aliases=["ttt"], usage="[opponent]")
    async def ttt(self, ctx, *, opponent: discord.Member):
        #Creates a message and reacts to it
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
        #Sets up the game class
        players = [ctx.author, opponent]
        random.shuffle(players)
        ctx.tttgame = TicTacToe(ctx, self.bot, msg, players)
        await ctx.tttgame.update(ctx.author)
        game = True
        #Game loop
        while game:
            for user in ctx.tttgame.players:
                try:
                    #Try doing a turn, return if if times out
                    await ctx.tttgame.turn(user)
                except asyncio.TimeoutError:
                    return await ctx.send("Tic Tac Toe has timed out")
                won = await ctx.tttgame.checkwin(user)
                if won == True:
                    #Announce winner and return if someone won
                    await ctx.tttgame.update(str(user) + " won 🎉!")
                    game = False
                    break
                if await ctx.tttgame.checktie() == True:
                    #Announce tie and return if tied
                    await ctx.tttgame.update("The game was a tie")
                    game = False
                    break
    
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(name="hangman", description="A hangman game")
    async def hangman(self, ctx):
        #Create a dict of tries and pictures
        pictures = {6:"https://upload.wikimedia.org/wikipedia/commons/8/8b/Hangman-0.png",
            5:"https://upload.wikimedia.org/wikipedia/commons/3/30/Hangman-1.png",
            4:"https://upload.wikimedia.org/wikipedia/commons/7/70/Hangman-2.png",
            3:"https://upload.wikimedia.org/wikipedia/commons/9/97/Hangman-3.png",
            2:"https://upload.wikimedia.org/wikipedia/commons/2/27/Hangman-4.png",
            1:"https://upload.wikimedia.org/wikipedia/commons/6/6b/Hangman-5.png",
            0:"https://upload.wikimedia.org/wikipedia/commons/d/d6/Hangman-6.png"}
        #Get the word
        await ctx.send("Please configure a word in your DMs")
        await ctx.author.send("What is your word?")
        def check(msg):
            return msg.author == ctx.author and msg.channel.id == ctx.author.dm_channel.id
        message = await self.bot.wait_for("message", check=check)
        #Create all the variables
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
            

            #Get the info on the reaction
            reaction, reaction_user = done.pop().result()
            
            #Get the guess
            ask = await ctx.send(f"{str(reaction_user)}: What is your guess?")
            def check(msg):
                return msg.author.id == reaction_user.id and msg.channel == reaction.message.channel
            reply = await self.bot.wait_for("message", check=check)

            #Check to make sure it's one letter
            if len(reply.content) != 1:
                await ctx.send("That not a letter", delete_after=5)

            #Check to make sure it's not already guessed
            elif reply.content in already_guessed:
                await ctx.send("You already guessed that", delete_after=5)
            
            #Check to make sure the letter is in the word
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
            
            #If it was a valid guess but not a correct one, announce invalid guess, and subtrac score
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
                #Clears up the turn async, so we can continue the game
                if ctx.guild.me.guild_permissions.manage_messages:
                    await asyncio.sleep(5)
                    await reply.delete()
                    await ask.delete()
            self.bot.loop.create_task(clearup(reply, ask))
            
            #If they guessed the whole, finish the game
            if word == guessed:
                em = self.bot.build_embed(title="Hangman", description="You won 🎉!")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Guesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)
                return await ctx.send("You won hangman!")
            
            #If they lost, finish the game
            if lives == 0:
                em = self.bot.build_embed(title="Hangman", description="You lost")
                em.add_field(name="Tries Remaining", value=str(lives))
                if len(incorrect) != 0:
                    em.add_field(name="Incorrect Gusesses", value=", ".join(incorrect))
                em.add_field(name="Guessing", value=guessed)
                em.set_thumbnail(url=pictures[lives])
                await game_msg.edit(embed=em)
                return await ctx.send(f"You lost hangman. The word was ||{word}||")
     


def setup(bot):
    bot.add_cog(Games(bot))