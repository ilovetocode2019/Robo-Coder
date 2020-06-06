from __future__ import unicode_literals

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

try:
    import youtube_dl
    youtube_dl_imported = True
except ModuleNotFoundError:
    youtube_dl_imported = False
    print("Youtube-dl is not found")

import re
from datetime import datetime as d
import requests
import importlib
import sys
import traceback

import functools
import itertools
import math

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
    def __init__(self, song, location, source, status):
        self.song = song
        self.location = location
        self.source = source
        self.status = status

    def __str__(self):
        return self.song

if youtube_dl_imported:
    class YTDLSource:
        YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        }

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

        ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

        def __init__(self, ctx: commands.Context, *, data: dict, volume: float = 0.5):

            self.data = data

            self.uploader = data.get('uploader')
            self.uploader_url = data.get('uploader_url')
            date = data.get('upload_date')
            self.upload_date = date[6:8] + '/' + date[4:6] + '/' + date[0:4]
            self.title = data.get('title')
            self.thumbnail = data.get('thumbnail')
            self.description = data.get('description')
            self.duration = self.parse_duration(int(data.get('duration')))
            self.tags = data.get('tags')
            self.url = data.get('webpage_url')
            self.views = data.get('view_count')
            self.likes = data.get('like_count')
            self.dislikes = data.get('dislike_count')
            self.stream_url = data.get('url')


        def __str__(self):
            return '**{0.title}** by **{0.uploader}**'.format(self)

        @classmethod
        async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
            loop = loop or asyncio.get_event_loop()
            
            if search.startswith("https:"):
                await ctx.send(f"🔎 Searching <{search}>")
            else:
                await ctx.send(f"🔎 Searching {search}")

            partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
            data = await loop.run_in_executor(None, partial)

            if data is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

            if 'entries' not in data:
                process_info = data
            else:
                process_info = None
                for entry in data['entries']:
                    if entry:
                        process_info = entry
                        break

                if process_info is None:
                    raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))
            

            webpage_url = process_info['webpage_url']

            partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=True)
            processed_info = await loop.run_in_executor(None, partial)

            if processed_info is None:
                raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

            if 'entries' not in processed_info:
                info = processed_info
            else:
                info = None
                while info is None:
                    try:
                        info = processed_info['entries'].pop(0)
                    except IndexError:
                        raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

            return cls.ytdl.prepare_filename(info), cls(ctx, data=info)

        @staticmethod
        def parse_duration(duration: int):
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{} days'.format(days))
            if hours > 0:
                duration.append('{} hours'.format(hours))
            if minutes > 0:
                duration.append('{} minutes'.format(minutes))
            if seconds > 0:
                duration.append('{} seconds'.format(seconds))

            return ', '.join(duration)

    class YTDLInfo:
        YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        }

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

        ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

        def __init__(self, ctx: commands.Context, *, data: dict, volume: float = 0.5):

            self.data = data

            self.uploader = data.get('uploader')
            self.uploader_url = data.get('uploader_url')
            date = data.get('upload_date')
            self.upload_date = date[6:8] + '/' + date[4:6] + '/' + date[0:4]
            self.title = data.get('title')
            self.thumbnail = data.get('thumbnail')
            self.description = data.get('description')
            self.duration = self.parse_duration(int(data.get('duration')))
            self.tags = data.get('tags')
            self.url = data.get('webpage_url')
            self.views = data.get('view_count')
            self.likes = data.get('like_count')
            self.dislikes = data.get('dislike_count')
            self.stream_url = data.get('url')

        def __str__(self):
            return '**{0.title}** by **{0.uploader}**'.format(self)

        @classmethod
        async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
            loop = loop or asyncio.get_event_loop()

            partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
            data = await loop.run_in_executor(None, partial)

            if data is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

            if 'entries' not in data:
                process_info = data
            else:
                process_info = None
                for entry in data['entries']:
                    if entry:
                        process_info = entry
                        break

                if process_info is None:
                    raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

            webpage_url = process_info['webpage_url']
            partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
            processed_info = await loop.run_in_executor(None, partial)

            if processed_info is None:
                raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

            if 'entries' not in processed_info:
                info = processed_info
            else:
                info = None
                while info is None:
                    try:
                        info = processed_info['entries'].pop(0)
                    except IndexError:
                        raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

            return cls(ctx, data=info)

        @staticmethod
        def parse_duration(duration: int):
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{} days'.format(days))
            if hours > 0:
                duration.append('{} hours'.format(hours))
            if minutes > 0:
                duration.append('{} minutes'.format(minutes))
            if seconds > 0:
                duration.append('{} seconds'.format(seconds))

            return ', '.join(duration)


class Player:

    def __init__(self, ctx, msg):
        self.announce = True
        self.msg = msg
        self.temporary = []
        self.now = None
        self.looping = False
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
            
            if self.now == None:
                try:
                    async with timeout(180):  # 3 minutes
                        self.now = await self.queue.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return
                
            if self.now.source is None:
                self.now.source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.now.location))
                self.voice.play(self.now.source, after=self.after_song)

            else:
                self.voice.play(self.now.source, after=self.after_song)
            # After it plays the song, it runs the after_song function
            if self.announce:
                await self.ctx.send(f"🎵 Playing {self.now.song}")
            self.now.status = "playing"

            await self.msg.edit(embed=self.player_update())

            # This next line basically "pauses" the while loop until the after_song
            # function is run
            await self.event.wait()
            
            self.now.source = None

            if not self.looping:
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
            if os.path.exists(song):
                os.remove(song)
            else:
                pass

        del self.bot.get_cog("Music").players[self.ctx.guild.id]


class Music(commands.Cog):
    """Music to listen to"""
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
                await msg.add_reaction("🔂")
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
        if ctx.guild.id in self.bot.config["homeservers"] or ctx.author.id in self.bot.owner_ids:
            return True
        return False

    async def player_emoji_update(self, reaction, user):
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
                player.now = None
                player.voice.stop()
                player.queue._queue.clear()

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


    @commands.Cog.listener("on_reaction_add")
    async def reaction_add(self, reaction, user):
        await self.player_emoji_update(reaction, user)
    @commands.Cog.listener("on_reaction_remove")
    async def reaction_remove(self, reaction, user):
        await self.player_emoji_update(reaction, user)

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
                song = Song(os.path.splitext(filename)[0], "music/"+filename, None, "in queue")
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
    @commands.command(name="play", descrcription="Play a song from youtube", usage="[name or url]")
    async def playurl(self, ctx, *, query):
        if not ctx.author.voice:
            return await ctx.send("Join a call")
        ctx.player = await self.get_player(ctx)
        if not ctx.player.voice:
            # This next line basically runs the join function like it was a command
            await ctx.invoke(self.join)
        if ctx.author not in ctx.player.voice.channel.members:
            return await ctx.send("You can't play without being in the call")

        if query.startswith("<") and query.endswith(">"):
            lookup = query[1:-1]
        else:
            lookup = query

        filename, info = await YTDLSource.create_source(ctx, lookup, loop=self.bot.loop)
        ctx.player.temporary.append(filename)
           
        song = Song(info.title, filename, None, "in queue")
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send("📄 Enqueued " + info.title)

        #ctx.player.temporary.append(url)

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
    @commands.command(name="loop", description="Loop/unloop music")
    async def loop(self, ctx):
        try:
            ctx.player = self.players[ctx.guild.id]
        except:
            return await ctx.send("Not playing")
        
        if not ctx.player.looping:
            ctx.player.looping = True
            await ctx.send("Now looping")
        else:
            ctx.player.looping = False
            await ctx.send("Now not looping")

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
        ctx.player.now = None
        ctx.player.voice.stop()
        ctx.player.queue._queue.clear()
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
        
    @commands.command(name="youtubeinfo", description="Get info on a youtube song")
    async def songinfo(self, ctx, *, query):
        song = await YTDLInfo.create_source(ctx, query, loop=self.bot.loop)

        if len(song.description) > 500:
            trail = "..."
        else:
            trail = ""
        em = discord.Embed(title=song.title, description=song.description[:500]+trail, color=0X00ff00)

        em.add_field(name="Duration", value=str(song.duration))
        em.add_field(name="Uploader", value=str(song.uploader))
        em.add_field(name="Views", value=str(song.views))
        em.add_field(name="Likes", value=str(song.likes))
        em.add_field(name="Dislikes", value=str(song.dislikes))

        if len(song.tags) > 15:
            trail = "..."
        else:
            trail = ""

        em.add_field(name="Tags", value=", ".join(song.tags[:15])+trail)
        em.add_field(name="Upload date", value=str(song.upload_date))

        em.set_thumbnail(url=song.thumbnail)
        
        await ctx.send(embed=em)

        del song


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
        await ctx.player.msg.add_reaction("🔂")
        await ctx.player.msg.add_reaction("❌")

    @commands.command(name="players", description="Get all the running players", hidden=True)
    @commands.is_owner()
    async def players(self, ctx):
        await ctx.send(f"The bot is in {len(self.players)} voice channels")
        


def setup(bot):
    bot.add_cog(Music(bot))