import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

class TicTacToeButton(discord.ui.Button):
    def __init__(self, parent, space):
        super().__init__(label="\u200b", style=discord.ButtonStyle.primary, row=int(space/3))
        self.parent = parent
        self.space = space

    async def callback(self, interaction):
        await self.parent.on_action(self.space, self, interaction)

class HangmanStartModal(discord.ui.Modal, title="Start Hangman"):
    word = discord.ui.TextInput(
        label="Word",
        placeholder="Enter a word for hangman",
        max_length=100
    )

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction):
        if not self.word.value.isalpha():
            return await interaction.response.send_message("The hangman game was not created because your word is invalid. Make sure your word only contains alphabet characters, and has no spaces.", ephemeral=True)

        await interaction.response.defer()
        view = HangmanView(self.word.value.lower(), interaction.user)
        view.message = await interaction.channel.send(embed=view.get_embed(), view=view)

class HangmanJumpBackView(discord.ui.View):
    def __init__(self, jump_url):
        super().__init__()
        self.add_item(discord.ui.Button(url=jump_url, label="Jump to Game"))

class HangmanGuessModal(discord.ui.Modal, title="Hangman Guess"):
    guess = discord.ui.TextInput(
        label="Guess",
        placeholder="Guess a letter",
        max_length=1
    )

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction):
        guess = self.guess.value.lower()

        if not guess.isalpha():
            return await interaction.response.send_message("You guess must be a letter in the alphabet.", ephemeral=True)

        if guess in self.parent.correct + self.parent.incorrect:
            return await interaction.response.send_message("This letter has already been guessed.", view=HangmanJumpBackView(interaction.message.jump_url), ephemeral=True)
        elif guess not in self.parent.word:
            self.parent.incorrect.append(guess)
            self.parent.guess_history.append(f"{interaction.user.mention} incorrectly guessed `{guess}` :x:")
            await interaction.response.send_message("Your guess was incorrect.", view=HangmanJumpBackView(interaction.message.jump_url), ephemeral=True)
        elif guess in self.parent.word:
            self.parent.correct.append(guess)
            self.parent.guess_history.append(f"{interaction.user.mention} correctly guessed `{guess}` :white_check_mark:")
            await interaction.response.send_message("Your guess was correct.", view=HangmanJumpBackView(interaction.message.jump_url), ephemeral=True)

        while len("\n".join(self.parent.guess_history)) > 1024:
            self.parent.guess_history.pop(-1)

        if all([True if letter in self.parent.correct else False for letter in self.parent.word]):
            self.parent.disable_buttons()
            self.parent.stop()
        elif len(self.parent.incorrect) == self.parent.ALLOWED_INCORRECT_GUESSES:
            self.parent.disable_buttons()
            self.parent.stop()

        await interaction.message.edit(embed=self.parent.get_embed(), view=self.parent)

class HangmanView(discord.ui.View):
    ALLOWED_INCORRECT_GUESSES = 6

    def __init__(self, word, creator):
        super().__init__(timeout=180)
        self.word = word
        self.incorrect = []
        self.correct = []
        self.guess_history = [f"{creator.mention} created the game"]
        self.creator = creator

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.primary)
    async def guess(self, interaction, button):
        if interaction.user == self.creator:
            return await interaction.response.send_message("You cannot guess in your own hangman game.", view=HangmanJumpBackView(interaction.message.jump_url), ephemeral=True)

        await interaction.response.send_modal(HangmanGuessModal(self))

    async def on_timeout(self):
        self.disable_buttons()
        await self.message.edit(content="This game has ended because it was inactive.", view=self)

    def get_embed(self):
        em = discord.Embed(title="Hangman", description="Use the button below to make a guess.", color=0x96c8da)
        em.set_author(name=self.creator, icon_url=self.creator.display_avatar.url)

        if all([True if letter in self.correct else False for letter in self.word]):
            em.description = ":tada: The word was guessed!"
        elif len(self.incorrect) == self.ALLOWED_INCORRECT_GUESSES:
            em.description = f"You ran out of guesses. The word was ||{self.word}||."

        word = " ".join([letter if letter in self.correct else "_" for letter in self.word])
        guesses_left = self.ALLOWED_INCORRECT_GUESSES-len(self.incorrect)

        em.set_thumbnail(url=f"https://raw.githubusercontent.com/ilovetocode2019/Robo-Coder/master/assets/hangman/hangman{guesses_left}.png")

        em.add_field(name="Word", value=discord.utils.escape_markdown(word))
        em.add_field(name="Incorrect Guesses", value=", ".join(self.incorrect) if self.incorrect else "No incorrect guesses yet.")
        em.add_field(name="Guesses Left", value=guesses_left)
        em.add_field(name="Action History", value="\n".join(self.guess_history) if self.guess_history else "No guess history yet.", inline=False)

        return em

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

class TicTacToeView(discord.ui.View):
    def __init__(self, players):
        super().__init__(timeout=180)

        self.players = players
        self.current_player = 0
        self.board = [None, None, None, None, None, None, None, None, None]

        for space in range(9):
            button = TicTacToeButton(self, space)
            self.add_item(button)

    async def on_action(self, space, button, interaction):
        if self.current_player == 0:
            button.label = "X"
            button.style = discord.ButtonStyle.danger
            button.disabled = True
            self.board[space] = True
            self.current_player = 1
        elif self.current_player == 1:
            button.label = "0"
            button.style = discord.ButtonStyle.success
            button.disabled = True
            self.board[space] = False
            self.current_player = 0

        for spaces in [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]:
            if self.board[spaces[0]] == self.board[spaces[1]] == self.board[spaces[2]] == True:
                winner = self.players[0]
                break
            elif self.board[spaces[0]] == self.board[spaces[1]] == self.board[spaces[2]] == False:
                winner = self.players[1]
                break
            else:
                winner = None

        tie = all([space is not None for space in self.board])

        if winner:
            self.disable_buttons()
            await interaction.response.edit_message(content=f"{self.players[0].mention} :x: vs. {self.players[1].mention} :o: \n:tada: {winner} won!", view=self)
            self.stop()
        elif tie:
            self.disable_buttons()
            await interaction.response.edit_message(content=f"{self.players[0].mention} :x: vs. {self.players[1].mention} :o: \nIt's a tie!", view=self)
            self.stop()
        else:
            await interaction.response.edit_message(content=f"{self.players[0].mention} :x: vs. {self.players[1].mention} :o: \nCurrent player is {self.players[self.current_player].mention}", view=self)

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    async def on_timeout(self):
        self.disable_buttons()
        await self.message.edit(content=f"{self.players[0]} :x: vs. {self.players[1]} :o: \nGame is inactive - No winner", view=self)

    async def interaction_check(self, interaction):
        if interaction.user in self.players and interaction.user != self.players[self.current_player]:
            await interaction.response.send_message("It isn't your turn.", ephemeral=True)
            return False
        elif interaction.user not in self.players:
            await interaction.response.send_message("You aren't in this game.", ephemeral=True)
            return False
        else:
            return True

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":video_game:"
        self.hangman_games = {}

        self.tictactoe_context_menu = app_commands.ContextMenu(name="Tic Tac Toe", callback=self.context_menu_tictactoe)
        self.bot.tree.add_command(self.tictactoe_context_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.tictactoe_context_menu.name, type=self.tictactoe_context_menu.type)

    def cog_check(self, ctx):
        return ctx.guild

    @commands.command(name="hangman", description="Play hangman in Discord", invoke_without_command=True)
    @commands.guild_only()
    async def hangman(self, ctx):
        try:
            await ctx.author.send("What is your word?")
        except discord.Forbidden:
            return await ctx.send("You don't have DMs enabled for this server. In order for you to secretly send me your word, either enable DMs in this server or use the `/hangman` slash command.")

        try:
            message = await self.bot.wait_for("message", check=lambda message: message.channel == ctx.author.dm_channel and message.author.id == ctx.author.id, timeout=180)
            word = message.content.lower()
        except asyncio.TimeoutError:
            return await ctx.send("The hangman game was not created because you didn't send your word in time.")

        if not word.isalpha():
            return await ctx.author.send("The hangman game was not created because your word is invalid. Make sure your word only contains alphabet characters, and has no spaces.")

        view = HangmanView(word, ctx.author)
        await ctx.send(embed=view.get_embed(), view=view)

    @app_commands.command(name="hangman", description="Start a hangman game")
    @commands.guild_only()
    async def hangman_slash(self, interaction):
        await interaction.response.send_modal(HangmanStartModal())

    @commands.hybrid_command(name="tictactoe", description="Play a game of tic tac toe", aliases=["ttt"])
    @commands.guild_only()
    async def tictactoe(self, ctx, *, opponent: discord.Member):
        if opponent == ctx.author:
            return await ctx.send("You cannot play against yourself.", ephemeral=True)
        if opponent.bot:
            return await ctx.send("You cannot play against a bot.", ephemeral=True)

        players = [ctx.author, opponent]
        random.shuffle(players)

        view = view=TicTacToeView(players)
        view.message = await ctx.send(f"{players[0].mention} :x: vs. {players[1].mention} :o: \nCurrent player is {players[0].mention}", view=view)

    async def context_menu_tictactoe(self, interaction, opponent: discord.Member):
        if opponent.bot:
            return await interaction.response.send_message("You cannot play against a bot.", ephemeral=True)

        players = [interaction.user, opponent]
        random.shuffle(players)

        view = view=TicTacToeView(players)
        view.message = await interaction.response.send_message(f"{players[0].mention} :x: vs. {players[1].mention} :o: \nCurrent player is {players[0].mention}", view=view)

async def setup(bot):
    await bot.add_cog(Games(bot))
