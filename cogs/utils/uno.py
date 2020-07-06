import discord
import random
import asyncio

class Game:
    def __init__(self, ctx):
        self.bot = ctx.bot
        self.owner = ctx.author
        self.ctx = ctx
        self.bot.loop.create_task(self.setup())
        self.players = []
        self.channels = {}
        self.deck = []
        self.hands = {}
        self.messages = {}
        self.game_finished = asyncio.Event()

        self.reversed = False
        self.color = None
        self.skip = False

    async def setup(self):
        self.role = await self.ctx.guild.create_role(name="UNO Game")
        overwrites = {
            self.ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.role: discord.PermissionOverwrite(read_messages=True),
            self.ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        self.category = await self.ctx.guild.create_category(name="Uno", overwrites=overwrites)
        self.main_channel = await self.ctx.guild.create_text_channel(name="main", category=self.category)
        self.voice = await self.ctx.guild.create_voice_channel(name="voice", category=self.category)

    async def add_player(self, player):
        self.players.append(player)
        await player.add_roles(self.role)
        overwrites = {
            self.ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            player: discord.PermissionOverwrite(read_messages=True),
            self.ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        self.channels[player] = await player.guild.create_text_channel(name=f"{player}", category=self.category, overwrites=overwrites)

    async def remove_player(self, player):
        self.players.remove(player)
        await player.remove_roles(self.role)
        await self.channels[player].delete()

    async def start_game(self):
        for color in ["red", "yellow", "blue", "green"]:
            self.deck.append(Card(color, 1))
            for number in list(range(1, 10)) + ["reverse", "add2", "skip"]:
                self.deck.append(Card(color, number))
                self.deck.append(Card(color, number))

        for x in range(4):
            self.deck.append(Card("wild", None))
            self.deck.append(Card("wild", "add4"))

        random.shuffle(self.deck)
        
        for player in self.players:
            self.hands[player] = []
            for x in range(7):
                self.hands[player].append(self.deck[0])
                self.deck.pop(0)
        
        for player in self.players:
            em = self.bot.build_embed(title="Your Hand")
            em.description = "\n".join([str(card) for card in self.hands[player]])
            em.add_field(name="Top", value=str(self.deck[0]))
            msg = await self.channels[player].send(embed=em)
            self.messages[player] = msg

        await self.main_channel.send("The uno game has started!")
        self.main_loop = self.bot.loop.create_task(self.game_loop())
    
    async def _turn(self, player):
        if self.skip:
            top = self.deck[0]
            if top.number == "add2":
                await self.main_channel.send(f"{str(player).capitalize()} is roced to skip and draw 2 cards.")
                for x in range(2):
                    self.hands[player].append(self.deck[-1])
                    self.deck.pop(-1)
            if top.number == "add4":
                await self.main_channel.send(f"{str(player).capitalize()} is forced to skip and draw 4 cards.")
                for x in range(2):
                    self.hands[player].append(self.deck[-1])
                    self.deck.pop(-1)
            if top.number == "skip":
                await self.main_channel.send(f"{str(player).capitalize()} is forced to skip.")

            self.skip = False
            em = self.bot.build_embed(title="Your Hand")
            em.description = "\n".join([str(card) for card in self.hands[player]])
            em.add_field(name="Top", value=str(self.deck[0]))
            await self.messages[player].edit(embed=em)
            return

        draw_message = None
        draw_times = 0
        to_delete = []

        await self.main_channel.send(f"It is now {player}'s turn")
        to_delete.append(await self.channels[player].send("It is your turn: \n'quit' to leave \n'draw' to draw \n'wild' to play a wild \n[color], [type] to place a card down"))
        def check(message):
            return message.author.id == player.id and message.channel.id == self.channels[player].id
        
        while True:
            message = await self.bot.wait_for("message", check=check)
            to_delete.append(message)
            if message.content == "wild":
                message.content = "wild, None"
            
            if message.content == "quit":
                await self.remove_player(player)
                await self.main_channel.send(f"{str(player).capitalize()} quit the game")
                return


            elif message.content == "draw":
                can_draw = True
                top = self.deck[0]
                for card in self.hands[player]:
                    if (str(card.color) == str(top.color)) or (str(card.color) == str(self.color)) or (str(card.number) == str(top.number)) or (str(card.color) == "wild"):
                        can_draw = False
                        break

                if not can_draw:
                    to_delete.append(await self.channels[player].send("❌ You cannot draw"))
                else:
                    draw_times += 1
                    self.hands[player].append(self.deck[-1])
                    self.deck.pop(-1)
                    em = self.bot.build_embed(title="Your Hand")
                    em.description = "\n".join([str(card) for card in self.hands[player]])
                    em.add_field(name="Top", value=str(self.deck[0]))
                    await self.messages[player].edit(embed=em)
                    if not draw_message:
                        draw_message = await self.main_channel.send(f"{str(player).capitalize()} drew a card ({draw_times} times)")
                    else:
                        await draw_message.edit(content=f"{str(player).capitalize()} drew a card ({draw_times} times)")

            elif ", " in message.content:
                color, number = message.content.split(", ")
                top = self.deck[0]
                if color.isdigit():
                    color = int(color)
                    
                if (str(color) == str(top.color)) or (str(color) == str(self.color)) or (str(number) == str(top.number)) or (str(color) == "wild"):
                    card = None
                    for x in enumerate(self.hands[player]):
                        if str(x[1].color) == color and str(x[1].number) == number:
                            card = x[0]
                            break

                    if card != None:
                        self.hands[player].pop(card)
                        self.deck = [Card(color, number)] + self.deck
                        break
                    else:
                       to_delete.append(await self.channels[player].send("❌ You do not have that card"))
                else:
                    to_delete.append(await self.channels[player].send("❌ That does not match the card on the top"))

                    
                
            else:
                to_delete.append(await self.channels[player].send("❌ That is a invalid move"))
        
        self.color = None
        if color == "wild":
            to_delete.append(await self.channels[player].send("What color is your wild?"))
            while True:
                message = await self.bot.wait_for("message", check=check)
                to_delete.append(message)
                if message.content in ["red", "yellow", "green", "blue"]:
                    self.color = message.content
                    to_delete.append(message)
                    break
                else:
                    to_delete.append(await self.channels[player].send("❌ That is not a valid color. Make sure your color is red, yellow, green, or blue"))

        if number in ["add2", "add4", "skip"]:
            self.skip = True

        if number == "reverse":
            if self.reversed:
                self.reversed = False
            else:
                self.reversed = True

        
        for x in self.players:
            em = self.bot.build_embed(title="Your Hand")
            em.description = "\n".join([str(card) for card in self.hands[x]])
            em.add_field(name="Top", value=str(self.deck[0]))
            await self.messages[x].edit(embed=em)
        
        wild_message = ""
        if color == "wild":
            wild_message = f" as {self.color}"
        await self.main_channel.send(f"{str(player).capitalize()} played a {self.deck[0]}{wild_message}. They have {len(self.hands[player])} cards.")

        for x in to_delete:
            try:
                await x.delete()
            except:
                pass

    def check_win(self):
        for player in self.players:
            if len(self.hands[player]) == 0:
                return player

    async def game_loop(self):
        counter = 0
        while True:
            player = self.players[counter]
            await self._turn(player)

            if len(self.players) < 2:
                self.game_finished.set()
                await self.cleanup()
                self.main_loop.cacnel()
                return

            win = self.check_win()
            if win != None:
                await self.ctx.send(f"{str(win)} has won uno! 🎉")
                await self.main_channel.send(f"{str(win)} has won uno! 🎉")
                self.game_finished.set()
                self.main_loop.cancel()
                await self.cleanup()
                return

            if not self.reversed:
                if len(self.players) == counter+1:
                    counter = 0 
                else:
                    counter += 1
            else:
                if counter == 0:
                    counter = len(self.players)-1
                else:
                    counter -= 1

    async def cleanup(self):
        for player in self.players:
            try:
                await self.channels[player].delete()
            except:
                pass

        try:
            await self.main_channel.delete()
        except:
            pass

        try:
            await self.voice.delete()
        except:
            pass

        try:
            await self.role.delete()
        except:
            pass

        try:
            await self.category.delete()
        except:
            pass




class Card:
    def __init__(self, color, number):
        self.color = color
        self.number = number
        if self.number == "None":
            self.number = None

    def __str__(self):
        emojis = {"red1": 705148450051981394, "red0": 705148450517286913, "red2": 705148450693578813, "red3": 705148450752430100, "red4": 705148450928459886, "red5": 705148450936717432, "red6": 705148451117203557, "red7": 705148451335176242, "yellow0": 705148452140482640, "red8": 705148452241145886, "red9": 705148452266573854, "redreverse": 705148452396466206, "redskip": 705148452396466256, "wild": 705148452916428892, "redadd2": 705148453151309835, "yellow5": 705148453201903720, "yellow4": 705148453319082145, "yellow1": 705148453340315799, "green4": 705148453436522547, "yellow7": 705148453616877568, "yellowreverse": 705148453868666962, "green5": 705148453897895936, "green1": 705148453927387186, "green3": 705148453927387206, "green7": 705148453927387248, "yellow9": 705148453961072772, "yellow2": 705148453969199125, "green2": 705148453986238665, "yellowadd2": 705148454006947841, "yellow3": 705148454011404429, "green0": 705148454032113744, "green9": 705148454116130867, "yellow6": 705148454141296681, "yellowskip": 705148454271320137, "green6": 705148454309199872, "blue5": 705148454317588491, "yellow8": 705148454359269437, "blue4": 705148454384566293, "blue2": 705148454435029063, "green8": 705148454451675186, "blue0": 705148454489292881, "blue7": 705148454493487214, "blue3": 705148454514458695, "blue1": 705148454535692409, "blue8": 705148454586023977, "greenreverse": 705148454594281502, "blue6": 705148454615122001, "greenskip": 705148454648807455, "blue9": 705148454673973285, "greenadd2": 705148454766248018, "blueadd2": 705190062601535840, "bluereverse": 705190061951549515, "blueskip": 705148687634137128, "wildadd4": 705187758657896448, "ace_spades": 705526463037964348, "king_spades": 705526463050416168}
        card = f"{self.color}{self.number or ''}"
        return f"{self.color}, {self.number} <:{card}:{emojis.get(card) or card}>"
