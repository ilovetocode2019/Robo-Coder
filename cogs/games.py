import asyncio
import random
import typing

import discord
from discord import app_commands
from discord.ext import commands

class HangmanStartModal(discord.ui.Modal, title="Start Hangman"):
    word = discord.ui.TextInput(label="Word", placeholder="Enter a word for hangman", min_length=3, max_length=50)

    async def on_submit(self, interaction):
        if not self.word.value.isalpha():
            return await interaction.response.send_message("Make sure the word uses valid characters and has no spaces.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        view = HangmanView(self.word.value.lower(), interaction.user)
        view.message = await interaction.edit_original_response(embed=view.embed, view=view)

class HangmanGuessModal(discord.ui.Modal, title="Hangman Guess"):
    guess = discord.ui.TextInput(label="Guess", placeholder="Guess a letter", max_length=1)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction):
        guess = self.guess.value.lower()

        if self.view.is_finished():
            return await interaction.response.send_message("The game is no longer active.", ephemeral=True)
        elif not guess.isalpha():
            return await interaction.response.send_message("This character is not allowed as a guess.", ephemeral=True)
        elif guess in self.view.correct + self.view.incorrect:
            return await interaction.response.send_message("This letter has already been guessed.", ephemeral=True)

        if guess in self.view.word:
            self.view.correct.append(guess)
            self.view.guess_history.append(f":white_check_mark: `{guess}` {interaction.user.mention}")
        elif guess not in self.view.word:
            self.view.incorrect.append(guess)
            self.view.guess_history.append(f":x:`{guess}` {interaction.user.mention}")

        while len("\n".join(self.view.guess_history)) > 1024:
            self.view.guess_history.pop(-1)

        if all([True if letter in self.view.correct else False for letter in self.view.word]) or len(self.view.incorrect) == self.view.ALLOWED_INCORRECT_GUESSES:
            for button in self.view.children:
                button.disabled = True
            self.view.stop()

        await interaction.response.edit_message(embed=self.view.embed, view=self.view)

class HangmanView(discord.ui.View):
    ALLOWED_INCORRECT_GUESSES = 6

    def __init__(self, word, creator):
        super().__init__()
        self.word = word
        self.incorrect = []
        self.correct = []
        self.guess_history = []
        self.creator = creator

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.primary)
    async def guess(self, interaction, button):
        if interaction.user == self.creator:
            return await interaction.response.send_message("You cannot guess in your own hangman game.",ephemeral=True)

        await interaction.response.send_modal(HangmanGuessModal(self))

    async def on_timeout(self):
        for button in self.children:
            button.disabled = True
        await self.message.edit(content=f"This game has ended because it was inactive. The word was ||{self.word}||", view=self)

    @property
    def embed(self):
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
        em.add_field(name="Incorrect Guesses", value=", ".join(self.incorrect) if self.incorrect else "None")
        em.add_field(name="Remaining Guesses", value=guesses_left)

        if self.guess_history:
            em.add_field(name="Guess History", value="\n".join(self.guess_history), inline=False)

        return em

class TicTacToeButton(discord.ui.Button):
    def __init__(self, position):
        super().__init__(label="\u200b", style=discord.ButtonStyle.primary, row=int(position / 3))
        self.position = position

    async def callback(self, interaction):
        if interaction.user != self.view.current:
            return await interaction.response.send_message("You have to wait your turn.", ephemeral=True)

        self.view.board[self.position] = self.view.current
        self.label = ["❌", "⭕"][self.view.players.index(self.view.current)]
        self.disabled = True

        for spaces in [
            [0, 1, 2], [3, 4, 5], [6, 7, 8], # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8], # Columns
            [0, 4, 8], [2, 4, 6] # Diagonals
        ]:

            if all(self.view.board[space] == self.view.current for space in spaces):
                self.view.stop()
                return await interaction.response.edit_message(
                    content=self.view.format_message_with(f":tada: {self.view.current.mention} won!"),
                    view=self.view,
                    allowed_mentions=discord.AllowedMentions(users=False)
                )
            elif all([space is not None for space in self.view.board]):
                self.view.stop()
                return await interaction.response.edit_message(
                    content=self.view.format_message_with("It's a tie!"),
                    view=self.view,
                    allowed_mentions=discord.AllowedMentions(users=False)
                )

        self.view.current, self.view.next = self.view.next, self.view.current
        await interaction.response.edit_message(
            content=self.view.format_message_with(f"Current player is {self.view.current.mention}"),
            view=self.view,
            allowed_mentions=discord.AllowedMentions(users=False)
        )

class TicTacToeView(discord.ui.View):
    def __init__(self, user, opponent):
        super().__init__()
        self.current, self.next = self.players = random.sample([user, opponent], 2)
        self.board = [None] * 9

        for x in range(9):
            self.add_item(TicTacToeButton(x))

    def stop(self):
        for item in self.children:
            item.disabled = True
        super().stop()

    async def on_timeout(self):
        await self.message.edit(content=self.format_message_with("Game over due to inactivity"), view=self, allowed_mentions=discord.AllowedMentions(users=False))

    def format_message_with(self, text):
        return f"{self.players[0].mention} :x:  |  {self.players[1].mention} :o: \n\n{text}"

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":video_game:"

        self._tictactoe_menu = app_commands.ContextMenu(name="Tic Tac Toe", callback=self.context_tictactoe)
        self.bot.tree.add_command(self._tictactoe_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self._tictactoe_menu)

    @commands.hybrid_command(name="hangman", description="Start a game of hangman with your friends")
    @app_commands.user_install()
    async def hangman(self, ctx):
        if ctx.interaction:
            return await ctx.interaction.response.send_modal(HangmanStartModal())

        try:
            await ctx.author.send("What is your word?")
        except discord.Forbidden:
            mention = await self.bot.tree.mention_for('hangman')
            return await ctx.send(f"To start a game, you must allow DMs or run {mention} instead.")

        try:
            message = await self.bot.wait_for("message", check=lambda message: message.channel == ctx.author.dm_channel and message.author.id == ctx.author.id, timeout=180)
            word = message.content.lower()
        except asyncio.TimeoutError:
            return await ctx.send("The hangman game was not created because you didn't send your word in time.")

        if not word.isalpha():
            return await ctx.author.send("Make sure the word contains no spaces and only alphabetical characters.")

        view = HangmanView(word, ctx.author)
        view.message = await ctx.send(embed=view.embed, view=view)

    @commands.hybrid_command(name="tictactoe", description="Play a game of tic tac toe", aliases=["ttt"])
    @app_commands.user_install()
    async def tictactoe(self, ctx, *, opponent: typing.Union[discord.Member, discord.User]):
        if opponent == ctx.author:
            return await ctx.send("You cannot play against yourself.", ephemeral=True)
        if opponent.bot:
            return await ctx.send("You cannot play against a bot.", ephemeral=True)

        view = view=TicTacToeView(ctx.author, opponent)
        view.message = await ctx.send(
            view.format_message_with(f"Current player is {view.players[0].mention}"),
            view=view,
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.user_install()
    async def context_tictactoe(self, interaction, opponent: discord.Member):
        if opponent == interaction.user:
            return await interaction.response.send_message("You cannot play against yourself.", ephemeral=True)
        if opponent.bot:
            return await interaction.response.send_message("You cannot play against a bot.", ephemeral=True)

        view = view=TicTacToeView(interaction.user, opponent)
        view.message = await interaction.response.send_message(
            view.format_message_with(f"Current player is {players[0].mention}"),
            view=view,
            allowed_mentions=discord.AllowedMentions(users=False)
        )

async def setup(bot):
    await bot.add_cog(Games(bot))
