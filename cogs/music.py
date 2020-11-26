import discord
from discord.ext import commands
from discord.ext import menus

from async_timeout import timeout
from urllib.parse import urlparse
import asyncio
import youtube_dl
import functools
import os
import random
import time
import logging

logger = logging.getLogger("robo_coder.music")

class Pages(menus.ListPageSource):
    def __init__(self, data):
        self.player = data
        super().__init__(list(data.queue._queue), per_page=10)

    async def format_page(self, menu, entries):
        player = self.player

        offset = menu.current_page * self.per_page

        looping = ""
        if player.looping_queue:
            looping = "(🔁 Looping)"

        em = discord.Embed(title=f"Queue {looping}", description="", color=0x66FFCC)
        queue = ""
        for i, song in enumerate(entries, start=offset):
            queue += f"\n{i+1}. [{song.title}]({song.url}) `{song.duration}` - {song.requester.mention}"

        em.description = queue

        total_duration = 0
        for song in player.queue._queue:
            total_duration+=song.total_seconds

        em.description += f"\n\n{Song.parse_duration(total_duration)} total"

        em.set_footer(text=f"{len(list(self.player.queue._queue))} songs | Page {menu.current_page+1}/{(int(len(list(self.player.queue._queue))/10))+1}")  

        return em

class Player:
    def __init__(self, ctx, vc):
        self.ctx = ctx
        self.bot = ctx.bot
        self.voice = vc
        self.downloaded = []

        self.queue = asyncio.Queue()
        self.event = asyncio.Event()

        self.now = None
        self.looping = False
        self.looping_queue = False
        self.notifications = True
        self.volume = .5
        self.restart = False

        self.loop = self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        while True:
            if not self.now:
                try:
                    async with timeout(180):
                        self.now = await self.queue.get()
                except asyncio.TimeoutError:
                    await self.voice.disconnect()
                    try:
                        self.bot.players.pop(self.ctx.guild.id)
                    except:
                        pass
                    self.cleanup()
                    return

            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.now.filename))
            self.voice.play(source, after=self.after_song)
            self.voice.source.volume = self.volume

            if self.notifications and not self.restart:
                await self.ctx.send(f":notes: Now playing {discord.utils.escape_mentions(self.now.title)}")

            self.restart = False
            self.song_started = time.time()
            await self.event.wait()
            self.event.clear()
            source.cleanup()

            if self.looping_queue and not self.looping and not self.restart:
                await self.queue.put(self.now)

            if not self.looping:
                self.now = None

    def after_song(self, e):
        if not e:
            self.event.set()
        else:
            raise e

    def cleanup(self):
        self.voice.stop()
        for song in self.downloaded:
            try:
                os.remove(song)
            except OSError as exc:
                pass

    def get_bar(self, seconds):
        bar = ""
        decimal = (time.time()-self.song_started)/seconds

        i = int(decimal*30)
        for x in range(30):
            if x == i:
                bar += "🔘"
            else:
                bar += "▬"

        return bar

    def create_embed(self):
        looping = ""
        if self.looping:
            looping = "(🔂 Looping)"

        playing = "▶️"
        if self.voice.is_playing():
            playing = "⏸️"

        em = discord.Embed(title=f"{playing} {self.now.title} {looping}", color=0x66FFCC)
        em.add_field(name="Duration", value=f"{Song.timestamp_duration(int(time.time()-self.song_started))}/{self.now.timestamp_duration} `{self.get_bar(self.now.total_seconds)}`")
        em.add_field(name="Url", value=f"[Click]({self.now.url})")
        em.add_field(name="Requester", value=f"{self.now.requester.mention}")
        em.set_thumbnail(url=self.now.thumbnail)
        return em

class YTDLError(commands.CommandError):
    pass

class Song:
    YTDL_OPTIONS = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": False,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }
    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx, *, data, volume=0.5):
        self.data = data

        self.requester = ctx.author
        self.filename = data["filename"]

        self.uploader = data.get("uploader")
        self.uploader_url = data.get("uploader_url")
        date = data.get("upload_date")
        self.date = data.get("upload_date")
        self.total_seconds = int(data.get("duration"))
        self.upload_date = date[6:8] + "." + date[4:6] + "." + date[0:4]
        self.title = data.get("title")
        self.thumbnail = data.get("thumbnail")
        self.description = data.get("description")
        self.duration = self.parse_duration(int(data.get("duration")))
        self.timestamp_duration = self.timestamp_duration(int(data.get("duration")))
        self.tags = data.get("tags")
        self.url = data.get("webpage_url")
        self.views = data.get("view_count")
        self.likes = data.get("like_count")
        self.dislikes = data.get("dislike_count")
        self.stream_url = data.get("url")

    def __str__(self):
        return "**{0.title}** by **{0.uploader}**".format(self)

    @classmethod
    async def from_youtube(cls, ctx, search, *, loop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError("Couldn't find anything that matches `{}`".format(search))

        if "entries" not in data:
            process_info = data
        else:
            process_info = None
            for entry in data["entries"]:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError("Couldn't find anything that matches `{}`".format(search))

        webpage_url = process_info["webpage_url"]
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=True)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError("Couldn't fetch `{}`".format(webpage_url))

        if "entries" not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info["entries"].pop(0)
                except IndexError:
                    raise YTDLError("Couldn't retrieve any matches for `{}`".format(webpage_url))

        filename = cls.ytdl.prepare_filename(info)
        info["filename"] = filename
        return filename, cls(ctx, data=info)

    @classmethod
    async def playlist(cls, ctx, search, *, loop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError("Couldn't find anything that matches `{}`".format(search))

        if "entries" not in data:
            data_list = data
        else:
            data_list = []
            for entry in data["entries"]:
                if entry:
                    data_list.append(entry)

            if len(data_list) == 0:
                raise YTDLError("Playlist is empty")

        return data_list

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration_str = []
        if days > 0:
            duration_str.append("{} days".format(days))
        if hours > 0:
            duration_str.append("{} hours".format(hours))
        if minutes > 0:
            duration_str.append("{} minutes".format(minutes))
        if seconds > 0:
            duration_str.append("{} seconds".format(seconds))

        return ", ".join(duration_str)

    @staticmethod
    def timestamp_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        duration = []

        if int(days) > 0:
            duration.append(days)
        if int(hours) > 0:
            duration.append(f"{int(hours)}")
            duration.append(f"{int(minutes):02d}")
        else:
            duration.append(int(minutes))
        duration.append(f"{int(seconds):02d}")

        return ":".join([str(x) for x in duration])

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":notes:"

    def cog_check(self, ctx):
        return ctx.guild

    async def get_bin(self, url):
        parsed = urlparse(url)
        newpath = "/raw" + parsed.path
        url = parsed.scheme + "://" + parsed.netloc + newpath
        async with self.bot.session.get(url) as response:
            data = await response.read()
            data = data.decode("utf-8")
            return data.split("\n")

    async def post_bin(self, content):
        async with self.bot.session.post("https://mystb.in/documents", data=content.encode("utf-8")) as resp:
            data = await resp.json()
            return f"https://mystb.in/{data['key']}"

    @commands.command(name="connect", description="Connect the bot to a voice channel", aliases=["join"])
    async def connect(self, ctx):
        if not ctx.author.voice:
            return await ctx.send(":x: You are not in any voice channel")
        if ctx.guild.id in self.bot.players:
            return await ctx.send(":x: Already connected to a voice channel")

        try:
            voice_client = await ctx.author.voice.channel.connect()
        except:
            client = None
            for voice in self.bot.voice_clients:
                if voice.guild.id == ctx.guild.id:
                    client = voice
                    break
            if client:
                await client.disconnect()

            return await ctx.send(":x: Failed to connect to voice")

        self.bot.players[ctx.guild.id] = Player(ctx, voice_client)
        player = self.bot.players[ctx.guild.id]
        await ctx.send(f"Connected to `{player.voice.channel.name}`")

    @commands.command(name="summon", description="Summon the bot to a different channel")
    async def summon(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author.voice:
            return await ctx.send("You are not in any voice channel")

        await player.voice.move_to(ctx.author.voice.channel)
        player.ctx = ctx
        await ctx.send(f"Now connected to `{ctx.author.voice.channel.name}` and bound to `{ctx.channel.name}`")

    @commands.command(name="play", description="Play a song", usage="[query]", aliases=["p"])
    async def play(self, ctx, *, query):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            await ctx.invoke(self.connect)
            player = self.bot.players.get(ctx.guild.id)
            if not player:
                return

        if not ctx.author in player.voice.channel.members:
            return

        query = query.strip("<>")
        if query.startswith("https:"):
            await ctx.send(f":mag: Searching <{query}>")
        else:
            await ctx.send(f":mag: Searching {query}")

        if "list=" in query:
            await ctx.send(":globe_with_meridians: Fetching playlist")
            songs = await Song.playlist(ctx, query, loop=self.bot.loop)
            for song in songs:
                filename, info = await Song.from_youtube(ctx, song["id"], loop=self.bot.loop)
                await player.queue.put(info)
                player.downloaded.append(filename)
        else:
            filename, info = await Song.from_youtube(ctx, query, loop=self.bot.loop)

            if player.voice.is_playing():
                await ctx.send(f":page_facing_up: Enqueued {info.title}")

        await player.queue.put(info)
        player.downloaded.append(filename)

    @commands.command(name="playbin", description="Play a list of songs", usage="[url]", aliases=["pb"])
    async def playbin(self, ctx, url):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            await ctx.invoke(self.connect)
            player = self.bot.players.get(ctx.guild.id)
            if not player:
                return

        if not ctx.author in player.voice.channel.members:
            return

        await ctx.send(":globe_with_meridians: Fetching playlist")
        songs = await self.get_bin(url=url)
        for url in songs:
            filename, info = await Song.from_youtube(ctx, url, loop=self.bot.loop)
            await player.queue.put(info)
            player.downloaded.append(filename)

    @commands.command(name="pause", description="Pause the music")
    async def pause(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        player.voice.pause()
        await ctx.send(":arrow_forward: Paused")

    @commands.command(name="resume", description="Resume the music")
    async def resume(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        player.voice.resume()
        await ctx.send(":pause_button: Resumed")

    @commands.command(name="startover", description="Restart the current song", aliases=["restart"])
    async def startover(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if not player.now:
            return

        player.restart = True

        if not player.looping:
            player.queue._queue.appendleft(player.now)

        player.voice.stop()

        await ctx.send(":rewind: Starting over")

    @commands.command(name="jump", description="Jump to a song in the queue")
    async def jump(self, ctx, position: int):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if not player.now:
            return

        position = position - 1

        for x in range(position):
            current = await player.queue.get()
            if player.looping_queue:
                await player.queue.put(current)

        player.voice.stop()
        song = player.queue._queue[0]
        await ctx.send(f":track_next: Jumped to {discord.utils.escape_mentions(song.title)}")

    @commands.command(name="skip", description="Skip the music")
    async def skip(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return
        if not player.now:
            return

        player.voice.stop()
        await ctx.send(":track_next: Skipped current song")

    @commands.group(name="loop", descrition="Loop/unloop the music", invoke_without_command=True)
    async def loop(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if player.looping:
            player.looping = False
            await ctx.send(":x::repeat_one: Unloopd song")
        else:
            player.looping = True
            await ctx.send(":repeat_one: Looped song")

    @loop.command(name="queue", description="Loop/unloop the queue")
    async def loop_queue(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if player.looping_queue:
            player.looping_queue = False
            await ctx.send(":x::repeat: Not looping queue")
        else:
            player.looping_queue = True
            await ctx.send(":repeat: Looping queue")

    @commands.command(name="shuffle", description="Shuffle the music queue")
    async def shuffle(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        random.shuffle(player.queue._queue)
        await ctx.send(":twisted_rightwards_arrows: Shuffled music")

    @commands.command(name="volume", description="Set the volume", usage="[volume]")
    async def volume(self, ctx, volume: int = None):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return
        if not player.voice.is_playing():
            return

        if not volume:
            return await ctx.send(f":loud_sound: {int(player.volume * 100)}")

        player.voice.source.volume = volume / 100
        player.volume = volume / 100
        await ctx.send(f":loud_sound: Volume set to {volume}")

    @commands.command(name="notify", description="Enable/disable player updates")
    async def notify(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if player.notifications:
            player.notifications = False
            await ctx.send(":no_bell: Notifications disabled")
        else:
            player.notifications = True
            await ctx.send(":bell: Notifications enabled")

    @commands.command(name="stop", description="Stop the music")
    async def stop(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        player.looping = False
        player.looping_queue = False
        player.queue._queue.clear()
        player.voice.stop()
        await ctx.send(":stop_button: Stopped music, cleared queue")

    @commands.command(name="now", description="Get the current playing song", aliases=["np"])
    async def now(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return
        if not player.now:
            return await ctx.send("Not playing anything")

        await ctx.send(embed=player.create_embed())

    @commands.group(name="queue", description="View the song queue", invoke_without_command=True)
    async def queue(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return
        if len(player.queue._queue) == 0:
            return await ctx.send("Queue is empty")

        pages = menus.MenuPages(source=Pages(player), clear_reactions_after=True)
        await pages.start(ctx)

    @queue.command(name="save", description="Save the queue")
    async def queue_save(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return

        if len(player.queue._queue) != 0:
            queue = [x.url for x in player.queue._queue]
            if player.looping_queue:
                queue = [player.now.url] + queue
            url = await self.post_bin(str("\n".join(queue)))
            await ctx.send(f"Playlist saved to {url}")
        else:
            await ctx.send("No queue to save")

    @queue.command(name="remove", description="Remove a song from the queue")
    async def queue_remove(self, ctx, index: int):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            return
        if not ctx.author in player.voice.channel.members:
            return
        if index == 0 or index > len(player.queue._queue):
            return await ctx.send("Index not found")

        to_remove = player.queue._queue[index-1]
        player.queue._queue.remove(to_remove)
        await ctx.send(f":wastebasket: Removed {to_remove.title} from queue")

    @commands.command(name="disconnect", description="Disconnect the bot from a voice channel", aliases=["leave"])
    async def disconnect(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if player:
            if not ctx.author in player.voice.channel.members:
                return

            if len(player.queue._queue) != 0:
                queue = [x.url for x in player.queue._queue]
                if player.looping_queue:
                    queue = [player.now.url] + queue
                url = await self.post_bin(str("\n".join(queue)))
                await ctx.send(f"Playlist saved to {url}")

            player.loop.cancel()
            await player.voice.disconnect()
            try:
                self.bot.players.pop(ctx.guild.id)
            except:
                pass
            player.cleanup()
        else:
            client = None
            for voice in self.bot.voice_clients:
                if voice.guild.id == ctx.guild.id:
                    client = voice
                    break
            if client:
                await client.disconnect()

        await ctx.send("Disconnected from voice")

    @commands.command(name="allplayers", description="View all players")
    @commands.is_owner()
    async def allplayers(self, ctx):
        if not self.bot.players:
            return await ctx.send("No players")

        await ctx.send("\n".join([f"{player.voice.guild} - `{player.voice.channel} | {player.ctx.channel}` ({player.voice.latency*1000}ms)" for player in self.bot.players.values()]))

    @commands.command(name="stopall", descrition="Stop all players")
    @commands.is_owner()
    async def stopall(self, ctx):
        for player in self.bot.players.values():
            if len(player.queue._queue) != 0:
                queue = [x.url for x in player.queue._queue]
                if player.looping_queue:
                    queue = [player.now.url] + queue
                url = await self.post_bin(str("\n".join(queue)))
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start again with `{ctx.prefix}playbin {url}`.")
            elif player.now:
                await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start your song again with the play command.")

            player.loop.cancel()
            player.cleanup()
            await player.voice.disconnect()

        self.bot.players = {}
        await ctx.send("All Players have been stopped")

    @commands.command(name="endplayer", description="Stops a single player")
    @commands.is_owner()
    async def endplayer(self, ctx, player: int):
        if player not in self.bot.players:
            return await ctx.send(":x: Could not find a player with that guild ID")

        player = self.bot.players[player]

        if len(player.queue._queue) != 0:
            queue = [x.url for x in player.queue._queue]
            if player.looping_queue:
                queue = [player.now.url] + queue
            url = await self.post_bin(str("\n".join(queue)))
            await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start again with `{ctx.prefix}playbin {url}`.")
        elif player.now:
            await player.ctx.send(f"Sorry! Your player has been stopped for maintenance. You can start your song again with the play command.")

        player.loop.cancel()
        await player.voice.disconnect()
        try:
            self.bot.players.pop(ctx.guild.id)
        except:
            pass
        player.cleanup()

        await ctx.send("Player has been stopped")

def setup(bot):
    bot.add_cog(Music(bot))
