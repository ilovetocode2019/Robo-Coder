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
import re

logger = logging.getLogger("robo_coder.music")

class SongPages(menus.ListPageSource):
    def __init__(self, songs):
        self.songs = songs
        super().__init__(songs, per_page=1)

    async def format_page(self, menu, song):

        em = discord.Embed(title=song.title, color=0x66FFCC)
        em.add_field(name="Duration", value=f"{song.timestamp_duration}")
        em.add_field(name="Url", value=f"[Click]({song.url})")
        em.set_thumbnail(url=song.thumbnail)
        em.set_footer(text=f"{len(self.songs)} results | Page {menu.current_page+1}/{len(self.songs)}")

        return em

class SongSelectorMenuPages(menus.Menu):
    """A special type of Menu dedicated to pagination.

    Attributes
    ------------
    current_page: :class:`int`
        The current page that we are in. Zero-indexed
        between [0, :attr:`PageSource.max_pages`).
    """
    def __init__(self, songs, **kwargs):
        self._source = SongPages(songs)
        self.songs = songs
        kwargs.setdefault("delete_message_after", True)

        self.current_page = 0
        self.result = None
        super().__init__(**kwargs)

    @property
    def source(self):
        """:class:`PageSource`: The source where the data comes from."""
        return self._source

    async def change_source(self, source):
        """|coro|

        Changes the :class:`PageSource` to a different one at runtime.

        Once the change has been set, the menu is moved to the first
        page of the new source if it was started. This effectively
        changes the :attr:`current_page` to 0.

        Raises
        --------
        TypeError
            A :class:`PageSource` was not passed.
        """

        if not isinstance(source, PageSource):
            raise TypeError('Expected {0!r} not {1.__class__!r}.'.format(PageSource, source))

        self._source = source
        self.current_page = 0
        if self.message is not None:
            await source._prepare_once()
            await self.show_page(0)

    def should_add_reactions(self):
        return self._source.is_paginating()

    async def _get_kwargs_from_page(self, page):
        value = await discord.utils.maybe_coroutine(self._source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return { 'content': value, 'embed': None }
        elif isinstance(value, discord.Embed):
            return { 'embed': value, 'content': None }

    async def show_page(self, page_number):
        page = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await self.message.edit(**kwargs)

    async def send_initial_message(self, ctx, channel):
        """|coro|

        The default implementation of :meth:`Menu.send_initial_message`
        for the interactive pagination session.

        This implementation shows the first page of the source.
        """
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        return await channel.send(**kwargs)

    async def start(self, ctx, *, channel=None, wait=False):
        await self._source._prepare_once()
        await super().start(ctx, channel=channel, wait=wait)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

    async def show_checked_page(self, page_number):
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_current_page(self):
        if self._source.is_paginating():
            await self.show_page(self.current_page)

    def _skip_double_triangle_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages <= 2

    @menus.button('\N{WHITE HEAVY CHECK MARK}', position=menus.First(0))
    async def select_page(self, payload):
        self.result = self.songs[self.current_page]
        self.stop()

    @menus.button('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f',
            position=menus.First(1), skip_if=_skip_double_triangle_buttons)
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button('\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f', position=menus.First(2))
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @menus.button('\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f', position=menus.Last(0))
    async def go_to_next_page(self, payload):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @menus.button('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f',
            position=menus.Last(1), skip_if=_skip_double_triangle_buttons)
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f', position=menus.Last(2))
    async def stop_pages(self, payload):
        """stops the pagination session."""
        self.stop()

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
    def __init__(self, ctx, voice):
        self.ctx = ctx
        self.bot = ctx.bot
        self.voice = voice

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

            if self.looping_queue and not self.looping and not self.restart:
                await self.queue.put(self.now)

            if not self.looping:
                self.now = None

    def after_song(self, e):
        if not e:
            self.event.set()
        else:
            raise e

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
        "outtmpl": "songs/%(extractor)s-%(id)s-%(title)s.%(ext)s",
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
    regex = re.compile("(?:https?://)?(?:www.)?(?:youtube.com|youtu.be)/(?:watch\\?v=)?([^\\s]+)")

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
    async def from_query(cls, ctx, search, *, loop, download=True):
        loop = loop or asyncio.get_event_loop()

        youtube_id = cls.regex.findall(search)

        if not youtube_id:
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

            try:
                webpage_url = process_info["webpage_url"]
            except:
                webpage_url = search

            try:
                song_id = process_info["song_id"]
                extractor = process_info["extractor"]
            except:
                song_id = None
                extractor = None

        else:
            webpage_url = youtube_id[0]
            extractor = "youtube"

        query = """SELECT *
                   FROM songs
                   WHERE songs.id=$1 AND songs.extractor=$2;
                """
        song = await ctx.bot.db.fetchrow(query, song_id, extractor)

        if song:
            return cls(ctx, data=song["data"])

        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=download)
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

        query = """INSERT INTO songs (id, filename, extractor, data)
                   VALUES ($1, $2, $3, $4);
                """
        await ctx.bot.db.execute(query, info["id"], filename, info["extractor"], info)

        return cls(ctx, data=info)

    @classmethod
    async def playlist(cls, ctx, search, *, loop, download=True, process=False):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=download, process=process)
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

        songs = []
        for song in data_list:
            song["filename"] = cls.ytdl.prepare_filename(song)
            songs.append(Song(ctx, data=song))
        return songs

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
        if ctx.guild.id in self.bot.players or ctx.guild.id in [voice.guild.id for voice in self.bot.voice_clients]:
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
                await player.queue.put(song)
        else:
            song = await Song.from_query(ctx, query, loop=self.bot.loop)
            if not song:
                return

            if player.voice.is_playing():
                await ctx.send(f":page_facing_up: Enqueued {song.title}")

            await player.queue.put(song)

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

        try:
            songs = await self.get_bin(url=url)
        except Exception as exc:
            return await ctx.send(":x: I couldn't fetch that bin. Make sure the url is valid.")

        for url in songs:
            song = await Song.from_query(ctx, url, loop=self.bot.loop)
            await player.queue.put(song)

    @commands.command(name="search", description="Search for a song on youtube")
    async def search(self, ctx, *, query):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            await ctx.invoke(self.connect)
            player = self.bot.players.get(ctx.guild.id)
            if not player:
                return

        if not ctx.author in player.voice.channel.members:
            return

        songs = await Song.playlist(ctx, f"ytsearch3:{query}", loop=self.bot.loop, download=False, process=True)

        pages = SongSelectorMenuPages(songs, clear_reactions_after=True)
        result = await pages.prompt(ctx)
        if not result:
            return await ctx.send("Not playing anything")

        song = await Song.from_query(ctx, result.data["id"], loop=self.bot.loop)

        if player.voice.is_playing():
            await ctx.send(f":page_facing_up: Enqueued {song.title}")

        await player.queue.put(song)

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

    @commands.command(name="jump", description="Jump to a song in the queue", aliases=["goto", "skipto", "jumpto"])
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

        player.loop.cancel()
        await player.voice.disconnect()
        try:
            self.bot.players.pop(ctx.guild.id)
        except:
            pass

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

        await ctx.send("Player has been stopped")

    @commands.Cog.listener("on_voice_state_update")
    async def delete_player_on_kick(self, member, before, after):
        player = self.bot.players.get(member.guild.id)

        if not player:
            return
        if member.id != self.bot.user.id:
            return

        if before.channel and not after.channel:
            player.loop.cancel()
            await player.voice.disconnect()
            try:
                self.bot.players.pop(member.guild.id)
            except:
                pass

    @commands.Cog.listener("on_voice_state_update")
    async def leave_on_inactivity(self, member, before, after):
        player = self.bot.players.get(member.guild.id)

        if not player:
            return

        members = [x for x in player.voice.channel.members if not x.bot]
        if len(members) > 0:
            return

        player.voice.pause()

        def check(member, before, after):
            return not member.bot and after.channel and after.channel.id == player.voice.channel.id

        try:
            await self.bot.wait_for("voice_state_update", timeout=180, check=check)
        except asyncio.TimeoutError:
            if len(player.queue._queue) != 0:
                queue = [x.url for x in player.queue._queue]
                if player.looping_queue:
                    queue = [player.now.url] + queue
                url = await self.post_bin(str("\n".join(queue)))
                await player.ctx.send(f"Playlist saved to {url}")

            player.loop.cancel()
            await player.voice.disconnect()
            try:
                self.bot.players.pop(player.guild.id)
            except:
                pass


def setup(bot):
    bot.add_cog(Music(bot))
