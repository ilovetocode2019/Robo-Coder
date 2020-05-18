from discord.ext import commands
from discord.ext import menus
import discord
import glob
import os
import asyncio
from async_timeout import timeout
from urllib.parse import urlparse
from aiohttp import ClientSession
import random

import re
from datetime import datetime as d
import requests
import importlib
import sys
import traceback

class PlayerMenu(menus.Menu):
    async def send_initial_message(self, ctx, channel):
        self.bot = ctx.bot
        self.guildid = ctx.guild.id
        em = discord.Embed(title="Player", color=0X00ff00)
        em.add_field(name="Playing", value="No song is playing", inline=False)
        return await channel.send(embed=em)

    def reaction_check(self, payload):

        if payload.user_id == self.bot.user.id:
            return False

        player = self.bot.get_cog("Music").players[self.guildid]
        

        if payload.message_id != self.message.id:
            return False

        if int(payload.user_id) not in [member.id for member in player.voice.channel.members]:
            return False
        
        return payload.emoji in self.buttons
    
    @menus.button("⏸️")
    async def pause(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]
        if player.voice.is_playing():
            player.voice.pause()
            player.now.status = "paused"
        elif player.voice.is_paused():
            player.voice.resume()
            player.now.status = "playing"
        else:
            pass
        await player.msg.edit(embed=player.player_update())
    @menus.button("⏹️")
    async def stop(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]
        player.queue._queue.clear()
        player.voice.stop()
        await player.msg.edit(embed=player.player_update())
    @menus.button("⏭️")
    async def skip(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]
        player.voice.stop()
        await player.msg.edit(embed=player.player_update())
    @menus.button("🔀")
    async def shuffle(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]
        random.shuffle(player.queue._queue)
        await player.msg.edit(embed=player.player_update())
    @menus.button("🆕")
    async def new(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]
        ask_msg = await self.ctx.send("What is your song name?")

        def check(msg):
            return msg.author.id == payload.user_id and msg.channel == self.ctx.channel

        msg = await self.bot.wait_for("message", check=check)
        query = msg.content
        if query+".mp3" not in os.listdir(os.getcwd()+"/music/"):
            return await self.ctx.send("Song not avalible")
        filename = "music/"+query+".mp3"
        #source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(filename))
        song = Song(query, None, "in queue")
        if player.voice.is_playing() or player.voice.is_paused():
            queue_msg = await self.ctx.send("📄 Enqueued " + query)
            if self.ctx.guild.me.guild_permissions.manage_messages:
                await queue_msg.delete()
        
        if self.bot.get_guild(self.guildid).me.guild_permissions.manage_messages:
            await msg.delete()
            await ask_msg.delete()

        await player.queue.put(song)
        await player.msg.edit(embed=player.player_update())

    @menus.button("❌")
    async def remove_song(self, payload):
        player = self.bot.get_cog("Music").players[self.guildid]

        ask_msg = await self.ctx.send("What is your song index?")

        def check(msg):
            return msg.author.id == payload.user_id and msg.channel == self.ctx.channel

        msg = await self.bot.wait_for("message", check=check)
        del player.queue._queue[int(msg.content)-1]
        await player.msg.edit(embed=player.player_update())
        okay_msg = await self.ctx.send("Removed song from queue")

        if self.bot.get_guild(self.guildid).me.guild_permissions.manage_messages:
            await okay_msg.delete()
            await msg.delete()
            await ask_msg.delete()


        await player.msg.edit(embed=player.player_update())

class Song():
    def __init__(self, song, source, status):
        self.song = song
        self.source = source
        self.status = status

    def __str__(self):
        return self.song


class Player:

    def __init__(self, ctx, msg, menu):
        self.announce = True
        self.msg = msg
        self.menu = menu
        self.temporary = []
        self.now = None
        self.queue = asyncio.Queue()

        self.voice = None
        self.ctx = ctx
        self.bot = ctx.bot

        self.event = asyncio.Event() # This will create a pause in the while loop until the song is finished

        self.main_loop = self.bot.loop.create_task(self.player_loop())

    def __del__(self):
        self.main_loop.cancel()

    async def player_loop(self):
        while True:
            # This clears the event var, which will pause the while loop while the song is playing
            self.event.clear()
            self.now = await self.queue.get()
            """try:
                async with timeout(180):  # 3 minutes
                    self.now = await self.queue.get()
            except asyncio.TimeoutError:
                self.bot.loop.create_task(self.stop())
                return"""
                
            if self.now.source is None:
                if self.now.song+".mp3" in os.listdir(os.getcwd()+"/music/"):
                    self.now.source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("music/"+self.now.song+".mp3"))
                else:
                    self.now.source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.now.song+".mp3"))
            self.voice.play(self.now.source, after=self.after_song)
            # After it plays the song, it runs the after_song function
            if self.announce:
                await self.ctx.send(f"🎵 Playing {self.now.song}")
            self.now.status = "playing"

            await self.msg.edit(embed=self.player_update())

            # This next line basically "pauses" the while loop until the after_song
            # function is run
            await self.event.wait()
            self.now = None
            await self.msg.edit(embed=self.player_update())

    def player_update(self):
        em = discord.Embed(title="Player", color=0X00ff00)
        if self.now != None:
            em.add_field(name="Playing", value=f"{str(self.now.song)} ({str(self.now.status)})", inline=False)
        else:
            em.add_field(name="Playing", value="No song is playing", inline=False)
        counter = 1
        queueshow = []
        for song in self.queue._queue:
            queueshow.append(str(counter) + "." + str(song))
            counter+=1
        if len(queueshow) != 0:
            em.add_field(name="Queue:", value="\n".join(queueshow), inline=False)
        return em

    def after_song(self, error):
        # This function catches any errors and starts up the while loop again
        if error:
            raise error
        else:
            self.event.set()

    async def stop(self):
        await self.menu.clear_buttons(react=True)
        self.queue._queue.clear()
        if self.voice:
            await self.voice.disconnect()
        for song in self.temporary:
            os.remove(song+".mp3")


class Music(commands.Cog):
    """Music for your server"""
    def __init__(self, bot):
        self.bot = bot

        self.players = {} # Each guild gets a player

    async def get_player(self, ctx):
        # This function finds the player for a guild or creates one
        player = self.players.get(ctx.guild.id)
        if not player:
            m = PlayerMenu()
            await m.start(ctx)
            player = Player(ctx, m.message, m)
            self.players[ctx.guild.id] = player

        return player

    def cog_unload(self):
        # This deletes all the Player instances
        for player in self.players.values():
            self.bot.loop.create_task(player.stop())
        for voice in self.bot.voice_clients:
            self.bot.loop.create_task(voice.disconnect())
   

    async def get_bin(self, url="https://hastebin.com", session=None):
        if not session:
            close_after = True
        session = session or ClientSession()
        parsed = urlparse(url)
        newpath = "/raw" + parsed.path
        url = parsed.scheme + "://" + parsed.netloc + newpath
        try:
            async with timeout(10):
                async with session.get(url) as resp:
                    f = await resp.read()
                    f = f.decode("utf-8")
        except asyncio.TimeoutError:
            if close_after:
                await session.close()
            raise TimeoutError("Could not fetch data: timed out.")
        if close_after:
            await session.close()
            return f


    @commands.command(name="newlist", description="Generate a playlist off of a keyword", usage="[search word]")
    async def newlist(self, ctx, *, keyword):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            await ctx.send("You cannot use music in a DM")

        ctx.player = await self.get_player(ctx)
        if not ctx.author.voice:
                return await ctx.send("Looks like you need to join a voice channel")
        if not ctx.player.voice:
                # This next line basically runs the join function like it was a command
                await ctx.invoke(self.join)
        counter = 0
        for filename in os.listdir(os.getcwd()+"/music/"):
            if keyword in filename:
                counter += 1
                song = Song(os.path.splitext(filename)[0], None, "in queue")
                await ctx.player.queue.put(song)


        await ctx.player.msg.edit(embed=ctx.player.player_update())


    @commands.command(name="playlist", description="Get playlist", usage="[bin url]")
    async def playlistget(self, ctx, site):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        ctx.player = await self.get_player(ctx)
        if not ctx.author.voice:
                return await ctx.send("Looks like you need to join a voice channel")
        if not ctx.player.voice:
                # This next line basically runs the join function like it was a command
                await ctx.invoke(self.join)
        await ctx.send("loading your playlist...")
        data = await self.get_bin(site)
        songs = data.split("\n")
        for query in songs:
            if not ctx.author.voice:
                return await ctx.send("Looks like you need to join a voice channel")
            if not ctx.player.voice:
                # This next line basically runs the join function like it was a command
                await ctx.invoke(self.join)
            if query+".mp3" not in os.listdir(os.getcwd()+"/music/"):
                return
            filename = "music/"+query+".mp3"
            song = Song(query, None, "in queue")

            await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())




    @commands.command(name="available", description="Search if a song is avalible", usage="[song name]")
    async def available(self, ctx, *, song):
        songs = os.listdir(os.getcwd()+"/music/")
        if song+".mp3" in songs:
            await ctx.send("That song is avalible")
        else:
            await ctx.send("Sorry, That song is not avalible")

    @commands.command(name="songs", description="Get a list of songs")
    async def songs(self, ctx):
        songs = sorted(os.listdir(os.getcwd()+"/music/"))
        viewsongs = []
        for song in songs:
            viewsongs.append(song.split(".mp3")[0])
        await ctx.send("```"+"\n".join(sorted(viewsongs))+"```")

    @commands.command(name="join", description = "Join a voice channel")
    async def join(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        if not ctx.author.voice:
            return await ctx.send("Please join a voice channel so I know where to go")
        ctx.player = await self.get_player(ctx)
        channel = ctx.author.voice.channel
        if ctx.player.voice:
            await ctx.player.voice.move_to(channel)
        else:
            ctx.player.voice = await channel.connect()
            
        await ctx.send("Joining your call")

    @commands.command(name="leave", description="Leave a voice channel")
    async def leave(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't end the call without being in the call")
        
        await ctx.player.stop()
        await ctx.send("Leaving")
        del self.players[ctx.guild.id]

    @commands.command(name="summon", description="Summon the bot to a new channel")
    async def summon(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        
        ctx.player.ctx = ctx
        await ctx.send("The music has now been summoned to this channel.")

    @commands.command(name="play", description="Play a song", usage="[song name]", aliases=["p"])
    async def play(self, ctx, *, query):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")
        if query+".mp3" not in os.listdir(os.getcwd()+"/music/"):
            return await ctx.send("Song not avalible")
        filename = "music/"+query+".mp3"
        song = Song(query, None, "in queue")
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + query)

        await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())

    @commands.command(name="playfile", descrcription="Play a link", usage="[file]")
    async def playfile(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")
        attachment_url = ctx.message.attachments[0].url
        file_request = requests.get(attachment_url)
        if file_request.headers["Content-Type"] != "audio/mpeg":
            return await ctx.send("❌ This is not a mpeg format")
        f = open(file_request.url.split("/")[-1], "wb")
        f.write(file_request.content)
        f.close()
        query = os.path.splitext(file_request.url.split("/")[-1])[0]
        song = Song(query, None, "in queue")
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + query)
        ctx.player.temporary.append(query)

        await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())

    @commands.command(name="playurl", descrcription="Play a link", usage="[link]")
    async def playurl(self, ctx, attachment_url):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")

        file_request = requests.get(attachment_url)
        if file_request.headers["Content-Type"] != "audio/mpeg":
            return await ctx.send("❌ This is not a mpeg format")
        f = open(file_request.url.split("/")[-1], "wb")
        f.write(file_request.content)
        f.close()
        query = os.path.splitext(file_request.url.split("/")[-1])[0]
        song = Song(query, None, "in queue")
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + query)
        ctx.player.temporary.append(query)

        await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())
    
        

    @commands.command(name="unqueue", description="Remove a song from the queue", usage="[number]")
    async def remove(self, ctx, number):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        del ctx.player.queue._queue[int(number)-1]
        await ctx.player.msg.edit(embed=ctx.player.player_update())
        await ctx.send("Removed song from queue")

    @commands.command(name="pause", description="Pause music")
    async def pause(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")

        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't pause the music without being in the call")
        if ctx.player.voice.is_playing():
            ctx.player.voice.pause()
            await ctx.send("Pausing ▶️")
            ctx.player.now.status = "paused"
            await ctx.player.msg.edit(embed=ctx.player.player_update())
        else:
            await ctx.send("Not playing")

    @commands.command(name="resume", description="Resume music")
    async def resume(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't resume the music without being in the call")
        if ctx.player.voice.is_paused():
            ctx.player.voice.resume()
            await ctx.send("Resumeing ⏸️")
            ctx.player.now.status = "playing"
            await ctx.player.msg.edit(embed=ctx.player.player_update())
        else:
            await ctx.send("Not playing")


    @commands.command(name="stop", description = "Stop the playing song")
    async def stop(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")

        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't stop without being in the call")
        ctx.player.queue._queue.clear()
        ctx.player.voice.stop()
        await ctx.send("Stopping ⏹️")
        

    @commands.command(name="skip", description="Skip the current song")
    async def skip(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't end the call without being in the call")
        ctx.player.voice.stop()
        await ctx.send("Skipped song ⏭️")

    @commands.command(name="shuffle", description="Shuffle all the music")
    async def shuffle(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't shuffle the music without being in the call")

        random.shuffle(ctx.player.queue._queue)
        await ctx.player.msg.edit(embed=ctx.player.player_update())
        await ctx.send("Shuffled 🔀")

    @commands.command(name="announce", description="Turn 'Now playing' announcments on/off")
    async def announce(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        
        if ctx.player.announce == False:
            ctx.player.announce = True
            await ctx.send("Now announcing")
        else:
            ctx.player.announce = False
            await ctx.send("Now not announcing")
        



    @commands.command(name="player", description="Bring the player embed down to the bottom", aliases=["np", "now"])
    async def player(self, ctx):
        if isinstance(ctx.channel, discord.channel.DMChannel):
            return await ctx.send("You cannot use music in a DM")

        try:
            self.players[ctx.guild.id]
            ctx.player = await self.get_player(ctx)
        except:
            return await ctx.send("No player exists.")

        ctx.player.msg = await ctx.send(embed=ctx.player.player_update())

        await ctx.player.msg.add_reaction("⏸️")
        await ctx.player.msg.add_reaction("⏹️")
        await ctx.player.msg.add_reaction("⏭️")
        await ctx.player.msg.add_reaction("🔀")
        await ctx.player.msg.add_reaction("🆕")
        await ctx.player.msg.add_reaction("❌")

    @commands.command(name="players", description="Get all the running players", hidden=True)
    @commands.is_owner()
    async def players(self, ctx):
        await ctx.send(f"The bot is in {len(self.players)} voice channels")
        


def setup(bot):
    bot.add_cog(Music(bot))