from discord.ext import commands
from discord.ext import menus
import discord
import glob
import os
import asyncio
from async_timeout import timeout
from urllib.parse import urlparse
from aiohttp import ClientSession
from io import BytesIO
import random

import re
from datetime import datetime as d
import requests
import importlib
import sys
import traceback

class MusicList(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=30)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        
        em = discord.Embed(title="Songs", description="")
        for i, song in enumerate(entries, start=offset):
            em.description += "\n" + song
        return em
            

class Song():
    def __init__(self, song, source, status):
        self.song = song
        self.source = source
        self.status = status

    def __str__(self):
        return self.song


class Player:

    def __init__(self, ctx, msg):
        self.announce = True
        self.msg = msg
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
        self.queue._queue.clear()
        if self.voice:
            await self.voice.disconnect()
        for song in self.temporary:
            os.remove(song+".mp3")


class Music(commands.Cog):
    """This cog is not for use on all servers. Run it yourself. The code is at https://github.com/ilovetocode2019/Robo-Coder/blob/master/cogs/music.py."""
    def __init__(self, bot):
        self.bot = bot

        self.players = {} # Each guild gets a player

    async def get_player(self, ctx):
        # This function finds the player for a guild or creates one
        player = self.players.get(ctx.guild.id)
        if not player:
            try:
                em = discord.Embed(title="Player", color=0X00ff00)
                em.add_field(name="Playing", value="No song is playing", inline=False)
                msg = await ctx.send(embed=em)
                await msg.add_reaction("⏸️")
                await msg.add_reaction("⏹️")
                await msg.add_reaction("⏭️")
                await msg.add_reaction("🔀")
                await msg.add_reaction("🆕")
                await msg.add_reaction("❌")
                player = Player(ctx, msg)
            except:
                pass
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

    async def get_song(self, url):
        async with ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    song = BytesIO(data)
                    return 200, song
                else:
                    return int(resp.status), None

    
    def cog_check(self, ctx):
        if ctx.guild.id in self.bot.config["homeservers"]:
            return True
        return False
    
    @commands.Cog.listener("on_reaction_add")
    async def reaction_add(self, reaction, user):
        try:
            player = self.players[reaction.message.guild.id]
        except:
            return
        if user != self.bot.user and reaction.message.id == player.msg.id and user in player.voice.channel.members:
            if str(reaction.emoji) == "⏸️":
                if player.voice.is_playing():
                    player.voice.pause()
                    #await reaction.message.channel.send("Pausing ▶️")
                    player.now.status = "paused"
                elif player.voice.is_paused():
                    player.voice.resume()
                    #await reaction.message.channel.send("Resumeing ⏸️")
                    player.now.status = "playing"
                else:
                    pass
            elif str(reaction.emoji) == "⏹️":
                player.queue._queue.clear()
                player.voice.stop()

            elif str(reaction.emoji) == "⏭️":
                player.voice.stop()

            elif str(reaction.emoji) == "🔀":
                random.shuffle(player.queue._queue)
                await player.msg.edit(embed=player.player_update())

                #await reaction.message.channel.send("Skipped song ⏭️")
            elif str(reaction.emoji) == "🆕":
                ask_msg = await reaction.message.channel.send("What is your song name?")
                def check(msg):
                    return msg.author == user and msg.channel == reaction.message.channel
                msg = await self.bot.wait_for("message", check=check)
                query = msg.content
                if query+".mp3" not in os.listdir(os.getcwd()+"/music/"):
                    return await reaction.message.channel.send("Song not avalible")
                filename = "music/"+query+".mp3"
                #source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(filename))
                song = Song(query, None, "in queue")
                if player.voice.is_playing() or player.voice.is_paused():
                    queue_msg = await reaction.message.channel.send("📄 Enqueued " + query)
                    if reaction.message.guild.me.guild_permissions.manage_messages:
                        await queue_msg.delete()
                
                if reaction.message.guild.me.guild_permissions.manage_messages:
                    await msg.delete()
                    await ask_msg.delete()



                await player.queue.put(song)

            elif str(reaction.emoji) == "❌":
                ask_msg = await reaction.message.channel.send("What is your song index?")
                def check(msg):
                    return msg.author == user and msg.channel == reaction.message.channel
                msg = await self.bot.wait_for("message", check=check)
                del player.queue._queue[int(msg.content)-1]
                await player.msg.edit(embed=player.player_update())
                okay_msg = await reaction.message.channel.send("Removed song from queue")

                if reaction.message.guild.me.guild_permissions.manage_messages:
                    await okay_msg.delete()
                    await msg.delete()
                    await ask_msg.delete()


            await player.msg.edit(embed=player.player_update())

    @commands.Cog.listener("on_reaction_remove")
    async def reaction_remove(self, reaction, user):
        try:
            player = self.players[reaction.message.guild.id]
        except:
            return
        if user != self.bot.user and reaction.message.id == player.msg.id and user in player.voice.channel.members:
            if str(reaction.emoji) == "⏸️":
                if player.voice.is_playing():
                    player.voice.pause()
                    #await reaction.message.channel.send("Pausing ▶️")
                    player.now.status = "paused"
                elif player.voice.is_paused():
                    player.voice.resume()
                    #await reaction.message.channel.send("Resumeing ⏸️")
                    player.now.status = "playing"
                else:
                    pass
            elif str(reaction.emoji) == "⏹️":
                player.queue._queue.clear()
                player.voice.stop()

            elif str(reaction.emoji) == "⏭️":
                player.voice.stop()

            elif str(reaction.emoji) == "🔀":
                random.shuffle(player.queue._queue)
                await player.msg.edit(embed=player.player_update())

                #await reaction.message.channel.send("Skipped song ⏭️")
            elif str(reaction.emoji) == "🆕":
                await reaction.message.channel.send("What is your song name?")
                def check(msg):
                    return msg.author == user and msg.channel == reaction.message.channel
                msg = await self.bot.wait_for("message", check=check)
                query = msg.content
                if query+".mp3" not in os.listdir(os.getcwd()+"/music/"):
                    return await reaction.message.channel.send("Song not avalible")
                filename = "music/"+query+".mp3"
                #source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(filename))
                song = Song(query, None, "in queue")
                if player.voice.is_playing() or player.voice.is_paused():
                    queue_msg = await reaction.message.channel.send("📄 Enqueued " + query)
                    if reaction.message.guild.me.guild_permissions.manage_messages:
                        await queue_msg.delete()
                
                if reaction.message.guild.me.guild_permissions.manage_messages:
                    await msg.delete()
                    await ask_msg.delete()

                await player.queue.put(song)

            elif str(reaction.emoji) == "❌":
                await reaction.message.channel.send("What is your song index?")
                def check(msg):
                    return msg.author == user and msg.channel == reaction.message.channel
                msg = await self.bot.wait_for("message", check=check)
                del player.queue._queue[int(msg.content)-1]
                await player.msg.edit(embed=player.player_update())
                await reaction.message.channel.send("Removed song from queue")

                if reaction.message.guild.me.guild_permissions.manage_messages:
                    await okay_msg.delete()
                    await msg.delete()
                    await ask_msg.delete()

            await player.msg.edit(embed=player.player_update())            

    @commands.guild_only()
    @commands.command(name="newlist", description="Generate a playlist off of a keyword", usage="[search word]")
    async def newlist(self, ctx, *, keyword):
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

    @commands.guild_only()
    @commands.command(name="playlist", description="Get playlist", usage="[bin url]")
    async def playlistget(self, ctx, site):
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
            
        pages = menus.MenuPages(source=MusicList(sorted(viewsongs)), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.guild_only()
    @commands.command(name="join", description = "Join a voice channel")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("Please join a voice channel so I know where to go")
        ctx.player = await self.get_player(ctx)
        channel = ctx.author.voice.channel
        if ctx.player.voice:
            await ctx.player.voice.move_to(channel)
        else:
            ctx.player.voice = await channel.connect()
            
        await ctx.send("Joining your call")


    @commands.guild_only()
    @commands.command(name="leave", description="Leave a voice channel")
    async def leave(self, ctx):
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

    @commands.guild_only()
    @commands.command(name="summon", description="Summon the bot to a new text channel")
    async def summon(self, ctx):
        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
        if not ctx.player.voice:
            return await ctx.send("Not in a call")
        
        ctx.player.ctx = ctx
        await ctx.send("The music has now been summoned to this channel.")

    @commands.guild_only()
    @commands.command(name="play", description="Play a song", usage="[song name]", aliases=["p"])
    async def play(self, ctx, *, query):
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
    

    @commands.guild_only()
    @commands.command(name="playfile", descrcription="Play a link", usage="[file]")
    async def playfile(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")
        attachment_url = ctx.message.attachments[0].url
        
        file_request = await self.get_song(attachment_url)
        """if file_request.headers["Content-Type"] != "audio/mpeg":
            return await ctx.send("❌ This is not a mpeg format")"""
        if file_request[0] != 200:
            return await ctx.send(str(file_request[0]))
        f = open(attachment_url.split("/")[-1], "wb")
        f.write(file_request[1].read())
        f.close()
        query = os.path.splitext(attachment_url.split("/")[-1])[0]
        song = Song(query, None, "in queue")
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + query)
        ctx.player.temporary.append(query)

        await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())
    
    @commands.guild_only()
    @commands.command(name="playurl", descrcription="Play a link", usage="[link]")
    async def playurl(self, ctx, attachment_url):
        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")

        file_request = await self.get_song(attachment_url)
        """if file_request.headers["Content-Type"] != "audio/mpeg":
            return await ctx.send("❌ This is not a mpeg format")"""
        if file_request[0] != 200:
            return await ctx.send(str(file_request[0]))
        f = open(attachment_url.split("/")[-1].split(".mp3")[0][:30]+".mp3", "wb")
        f.write(file_request[1].read())
        f.close()
        query = attachment_url.split("/")[-1].split(".mp3")[0][:30]
        song = Song(query, None, "in queue")
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + query)
        ctx.player.temporary.append(query)

        await ctx.player.queue.put(song)

        await ctx.player.msg.edit(embed=ctx.player.player_update())
    
        
    @commands.guild_only()
    @commands.command(name="unqueue", description="Remove a song from the queue", usage="[number]")
    async def remove(self, ctx, number):
        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
            
        del ctx.player.queue._queue[int(number)-1]
        await ctx.player.msg.edit(embed=ctx.player.player_update())
        await ctx.send("Removed song from queue")

    @commands.guild_only()
    @commands.command(name="pause", description="Pause music")
    async def pause(self, ctx):
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

    @commands.guild_only()
    @commands.command(name="resume", description="Resume music")
    async def resume(self, ctx):
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

    @commands.guild_only()
    @commands.command(name="stop", description = "Stop the playing song")
    async def stop(self, ctx):
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
        
    @commands.guild_only()
    @commands.command(name="skip", description="Skip the current song")
    async def skip(self, ctx):
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

    @commands.guild_only()
    @commands.command(name="shuffle", description="Shuffle all the music")
    async def shuffle(self, ctx):
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

    @commands.guild_only()
    @commands.command(name="announce", description="Turn 'Now playing' announcments on/off")
    async def announce(self, ctx):
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
        


    @commands.guild_only()
    @commands.command(name="player", description="Bring the player embed down to the bottom", aliases=["np", "now"])
    async def player(self, ctx):
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