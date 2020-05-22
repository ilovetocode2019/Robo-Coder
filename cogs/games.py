from discord.ext import commands
import discord
import asyncio
import random

class Complete(Exception):
    pass

class Card:
    def __init__(self, kind, specific):
        self.kind = kind
        self.specific = specific

class Uno:
    def __init__(self, ctx, bot, players, playerchanns, category, general, channels, voice):
        #Creates all the variables
        self.ctx = ctx
        self.bot = bot
        self.players = players
        self.playerchanns = playerchanns
        self.category = category
        self.general = general
        self.channels = channels
        self.voice = voice
        self.emojis = {"red1": 705148450051981394, "red0": 705148450517286913, "red2": 705148450693578813, "red3": 705148450752430100, "red4": 705148450928459886, "red5": 705148450936717432, "red6": 705148451117203557, "red7": 705148451335176242, "orange0": 705148452140482640, "red8": 705148452241145886, "red9": 705148452266573854, "redreverse": 705148452396466206, "redskip": 705148452396466256, "wild": 705148452916428892, "redadd2": 705148453151309835, "yellow5": 705148453201903720, "yellow4": 705148453319082145, "yellow1": 705148453340315799, "green4": 705148453436522547, "yellow7": 705148453616877568, "yellowreverse": 705148453868666962, "green5": 705148453897895936, "green1": 705148453927387186, "green3": 705148453927387206, "green7": 705148453927387248, "yellow9": 705148453961072772, "yellow2": 705148453969199125, "green2": 705148453986238665, "yellowadd2": 705148454006947841, "yellow3": 705148454011404429, "green0": 705148454032113744, "green9": 705148454116130867, "yellow6": 705148454141296681, "yellowskip": 705148454271320137, "green6": 705148454309199872, "blue5": 705148454317588491, "yellow8": 705148454359269437, "blue4": 705148454384566293, "blue2": 705148454435029063, "green8": 705148454451675186, "blue0": 705148454489292881, "blue7": 705148454493487214, "blue3": 705148454514458695, "blue1": 705148454535692409, "blue8": 705148454586023977, "greenreverse": 705148454594281502, "blue6": 705148454615122001, "greenskip": 705148454648807455, "blue9": 705148454673973285, "greenadd2": 705148454766248018, "blueskip" : 705148687634137128, "wildadd4" : 705187758657896448,  "bluereverse" : 705190061951549515, "blueadd2" : 705190062601535840}
        self.msgs = {}
        self.deck = []
        self.discard = []
        self.hands = {}
        self.color = "No"
        self.skip = True
        self.mode = True
        #Creates the cards
        for color in ["red", "yellow", "green", "blue"]:
            self.deck.append(Card(color, "skip"))
            numbers = list(range(1, 10))
            numbers.extend(["skip", "reverse", "add2"])
            for number in numbers:
                self.deck.append(Card(color, number))
                self.deck.append(Card(color, number))
        for x in range(4):
            self.deck.append(Card("wild", None))
            self.deck.append(Card("wild", "add4"))
        #Shuffles the cards
        random.shuffle(self.deck)
        
        #Distributes the cards
        for key in self.players:
            self.hands[key] = []
            for i in range(7):
                card = random.choice(self.deck)
                self.hands[key].append(card)
                self.deck.remove(card)

    async def begin(self):
        #Announce the game is starting
        await self.general.send("The game is starting")

        #Show the deck to each player
        for user in self.players:
            hand = []
            for card in self.hands[user]:
                specific = card.specific
                if card.specific == None:
                    specific = ""
                ID = str(self.emojis[str(card.kind) + str(specific)])
                emoji = str(card.kind) + str(specific)
                hand.append("<:"+emoji+":"+ID+">")
            self.msgs[user] = await self.playerchanns[user].send("The game is starting, Here is your deck:\n" + " ".join(hand))

    async def turn(self, user):
        #Check if the user is supposed to skip
        if self.deck[len(self.deck)-1].specific == "skip" and self.skip == True:
            self.skip = False
            return
        #Announce the users turn
        await self.general.send("It is now " + str(user) + "'s turn")
        
        #Draws some cards if there is a +2 card
        if self.deck[len(self.deck)-1].specific == "add2" and self.skip == True:
            for i in range(2):
                self.hands[user].append(self.deck[0])
                self.deck.pop(0)
            await self.msgs[user].edit(content="It's not your turn." + self.get_hand(user))
            await self.general.send(str(user) + " drew 2 cards and skiped there turn because the discard card was a add2 card")
            self.skip = False
            return
        if self.deck[len(self.deck)-1].specific == "add4" and self.skip == True:
            for i in range(4):
                self.hands[user].append(self.deck[0])
                self.deck.pop(0)
            await self.msgs[user].edit(content="It's not your turn." + self.get_hand(user))
            await self.general.send(str(user) + " drew 4 cards and skiped there turn because the discard card was a add4 card")
            self.skip = False
            return
                

        #Have them play there turn
        counter = 0
        def check(ms):
            #This function checks to make sure the message is the right use and channel
            return ms.author == user and ms.channel == self.playerchanns[user]
        while True:
            #Get the hand
            hand = self.get_hand(user)
            #Get the top card
            card = self.deck[len(self.deck)-1]
            specific = card.specific
            if card.specific == None:
                specific = ""
            ID = str(self.emojis[str(card.kind) + str(specific)])
            emoji = str(card.kind) + str(specific)
            #Loop there turn until they enter a valid card
            while True:
                await self.msgs[user].edit(content=hand + "\nThe top of the discard pile: <:"+emoji+":"+ID+">" + "\nWhat is your move?Type \"draw\" to draw. If you need to leave just type \"quit\"")
                msg = await self.bot.wait_for("message", check=check)
                if ", " in msg.content or msg.content == "draw" or msg.content == "quit":
                    break
                else:
                    await msg.delete()
            if msg.content == "quit":
                #If user quits
                self.players.remove(user)
                await self.playerchanns[user].delete()
                self.channels.remove(self.playerchanns[user])
                self.playerchanns.pop(user)
                self.msgs.pop(user)
                return

            if msg.content == "draw":
                #If user draws
                frontcard = self.deck[len(self.deck)-1]
                color = frontcard.kind
                if frontcard.kind == "wild":
                    color = self.color
                draw = True
                for card in self.hands[user]:
                    if str(color) == str(card.kind) or str(frontcard.specific) == str(card.specific) or str(card.kind) == "wild":
                        draw = False
                if draw == True:
                    self.hands[user].append(self.deck[0])
                    self.deck.pop(0)
                    await self.general.send(str(user) + " drew a card")
            
            if msg.content != "draw":
                #If they don't draw or quit, it will split the card into a kind and a specific of a kind
                kind, specific = msg.content.split(", ")
            await msg.delete()
    
            if msg.content != "draw":
                #If user wants to play a card
                frontcard = self.deck[len(self.deck)-1]
                color = frontcard.kind
                if frontcard.kind == "wild":
                    color = self.color
                #Check if the card is valid
                if str(kind) == str(color) or str(specific) == str(frontcard.specific) or kind == "wild":
                    #If it is check if the card exists in the users
                    correctcard = False
                    for usercard in self.hands[user]:
                        if str(kind)+str(specific) == str(usercard.kind)+str(usercard.specific):
                            correctcard = usercard
                    #If the card was found
                    if correctcard != False:
                        #Remove it from the hand and add it to the discard pile (The back of the deck)
                        self.deck.append(correctcard)
                        self.hands[user].remove(correctcard)
                        #If it's a wild ask what color the wild is
                        if correctcard.kind == "wild":
                            await self.msgs[user].edit(content="What color does your wild repersent?")
                            color = await self.bot.wait_for("message", check=check)
                            self.color = color.content
                            await color.delete()
                        #If it's a skip set the skip var to True. That way it will skip the next users turn
                        if correctcard.specific == "skip" or correctcard.specific == "add2" or correctcard.specific == "add4":
                            self.skip = True
                        #Then leave the turn loop
                        break
        
        wildcolor = ""
        if correctcard.kind == "wild":
            wildcolor = " as " + self.color
        #Get the updated hand
        hand = self.get_hand(user)
        #Edit the users msg and then announce what happend for the users turn in the main chat
        await self.msgs[user].edit(content="It's not your turn." + hand)
        await self.general.send(str(user) + " made is the move: " + msg.content + wildcolor + ". Now they have " + str(len(self.hands[user])) + " cards")
        #If the card is a reverse card make sure to reverse the turns
        if specific == "reverse":
            made_true = False
            if self.mode == False:
                self.mode = True
                made_true = True
            if self.mode == True and made_true == False:
                self.mode = False

    def get_hand(self, user):
        #This function basicly just gets the hand
        hand = []
        #Go though each card in the users hand as a Card object
        for card in self.hands[user]:
            specific = card.specific
            if card.specific == None:
                specific = ""
            #Get the emoji id and name
            ID = str(self.emojis[str(card.kind) + str(specific)])
            emoji = str(card.kind) + str(specific)
            hand.append("<:"+emoji+":"+ID+">")
        hand = " ".join(hand)
        #Return the hand with all the card emojis
        return hand

    async def checkwin(self):
        #This function checks for a win by looking for any empty hands
        for user in self.players:
            if len(self.hands[user]) == 0:
                await self.general.send(str(user) + " has won 🎉!")
                return True
            else:
                return False
                
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
            await self.msg.edit(content="Sorry. The game has timed out.", embed=None)

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
        self.opengames = {}
        self.unogames = {}
        self.tttgames = {}
    
    @commands.cooldown(1, 60)
    @commands.command(name="uno", description="Start a uno game")
    async def start(self, ctx):
        #Setup the game
        if ctx.guild.id in self.opengames or ctx.guild.id in self.unogames:
            return await ctx.send("Sorry. A game is already going. You can start a new game when the current game finishes.")
        #Creates a new game where people can join
        msg = await ctx.send("Starting a game. Click the check below to join.")
        cat = await ctx.guild.create_category("uno")
        new_channel = await ctx.guild.create_text_channel("uno-general", category=cat)
        await new_channel.send("The game will start shortly.")
        voice = await ctx.guild.create_voice_channel("Uno", category=cat)
        self.opengames[ctx.guild.id] = [str(msg), cat, new_channel, [], {}, []]
        #Add a reaction to let people join
        await msg.add_reaction("✅")
        #Gives the reaction time to be cliked
        await asyncio.sleep(20)
        #This checks if enough people have joined the game
        self.unogames[ctx.guild.id] = Uno(ctx, self.bot, self.opengames[ctx.guild.id][5], self.opengames[ctx.guild.id][4], self.opengames[ctx.guild.id][1], self.opengames[ctx.guild.id][2], self.opengames[ctx.guild.id][3], voice)
        self.opengames.pop(ctx.guild.id)
        if len(self.unogames[ctx.guild.id].players) < 2:
            if ctx.guild.id not in self.unogames:
                return await ctx.send("Your already cleared.")
            await self.unogames[ctx.guild.id].general.delete()
            await self.unogames[ctx.guild.id].voice.delete()
            for channel in self.unogames[ctx.guild.id].channels:
                await channel.delete()
            await self.unogames[ctx.guild.id].category.delete()
            self.unogames.pop(ctx.guild.id)
            return await ctx.send("Not enough people have joined the game.")
        #Starts the game
        await ctx.send("This game has started. When the current game is complete, you can start a new one.")
        await self.games[ctx.guild.id].begin()
        #Game loop where players can do moves
        try:
            counter = 0
            while True:
                #User the turn method to give the player a turn
                await self.unogames[ctx.guild.id].turn(self.unogames[ctx.guild.id].players[counter])
                #If moving foward though the players
                finished = await self.unogames[ctx.guild.id].checkwin()
                if finished == True:
                    break
                if self.unogames[ctx.guild.id].mode:
                    if counter != len(self.unogames[ctx.guild.id].players)-1:
                        counter += 1
                    else:
                        counter = 0
                #If moving backwards though the players
                else:
                    if counter != 0:
                        counter -= 1
                    else:
                        counter = len(self.unogames[ctx.guild.id].players)-1
        except:
            pass
        #When the game finishes
        await self.unogames[ctx.guild.id].general.send("Game over. You have 30 seconds before all channels are deleted")
        await asyncio.sleep(30)
        #This cleans up after the game
        if ctx.guild.id not in self.unogames:
            return await ctx.send("Your already cleared.")
        await self.unogames[ctx.guild.id].general.delete()
        await self.unogames[ctx.guild.id].voice.delete()
        for channel in self.games[ctx.guild.id].channels:
            await channel.delete()
        await self.unogames[ctx.guild.id].category.delete()
        self.games.pop(ctx.guild.id)
        await ctx.send("The game on this server is over. You can start a new one whenever you want")


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
                

    @commands.Cog.listener("on_reaction_add")
    async def reaction(self, reaction, user):
        #This function waits for a reaction
        if reaction.message.guild.id in self.opengames and not user.bot and reaction.emoji == "✅":
            if str(reaction.message) == self.opengames[reaction.message.guild.id][0] and user != self.bot.user:
                #Announce the join
                await reaction.message.channel.send(str(user) + " has joined the game")
                overwrites = {
                    reaction.message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    reaction.message.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                #Create the channel and add the user and channel to some lists and dicts
                new_channel = await reaction.message.guild.create_text_channel("uno "+str(user), category=self.opengames[reaction.message.guild.id][1], overwrites=overwrites)
                self.opengames[reaction.message.guild.id][4][user] = new_channel
                self.opengames[reaction.message.guild.id][5].append(user)
                self.opengames[reaction.message.guild.id][3].append(new_channel)

def setup(bot):
    bot.add_cog(Games(bot))