import discord
from discord.ext import commands, menus

import asyncio
import datetime
import functools
import humanize
import itertools
import logging
import os
import random
import re
import sys
import time
import urllib
import youtube_dl

from .utils import errors, formats, human_time

log = logging.getLogger("robo_coder.music")

class SearchPages(menus.ListPageSource):
    def __init__(self, songs):
        self.songs = songs
        super().__init__(songs, per_page=1)

    async def format_page(self, menu, song):
        em = discord.Embed(title=song.title, color=0x66FFCC)
        em.set_thumbnail(url=song.thumbnail)
        em.add_field(name="Duration", value=f"{song.timestamp_duration}")
        em.add_field(name="Url", value=f"[Click]({song.url})")
        em.add_field(name="Uploader", value=f"[{song.uploader}]({song.uploader_url})")
        em.set_footer(text=f"{len(self.songs)} results | Page {menu.current_page+1}/{len(self.songs)}")
        return em

class SongSelectorMenuPages(menus.MenuPages):
    def __init__(self, songs, **kwargs):
        self.songs = songs
        self.current_page = 0
        self.result = None

        kwargs.setdefault("delete_message_after", True)
        kwargs.setdefault("source", SearchPages(songs))
        super().__init__(**kwargs)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

    # Even though we are subclassing MenuPages, which has this, I need to define it here so I can use it in the decorator
    def _skip_double_triangle_buttons(self):
        max_pages = self._source.get_max_pages()
        if max_pages is None:
            return True
        return max_pages <= 2

    @menus.button("\N{WHITE HEAVY CHECK MARK}", position=menus.First(0))
    async def select_page(self, payload):
        self.result = self.songs[self.current_page]
        self.stop()

    @menus.button("\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f", position=menus.First(1), skip_if=_skip_double_triangle_buttons)
    async def go_to_first_page(self, payload):
        await self.show_page(0)

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f", position=menus.First(2))
    async def go_to_previous_page(self, payload):
        await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f", position=menus.Last(0))
    async def go_to_next_page(self, payload):
        await self.show_checked_page(self.current_page + 1)

    @menus.button("\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f", position=menus.Last(1), skip_if=_skip_double_triangle_buttons)
    async def go_to_last_page(self, payload):
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @menus.button("\N{BLACK SQUARE FOR STOP}\ufe0f", position=menus.Last(2))
    async def stop_pages(self, payload):
        self.stop()

class QueuePages(menus.ListPageSource):
    def __init__(self, data):
        self.player = data
        super().__init__(list(data.queue), per_page=10)

    async def format_page(self, menu, entries):
        player = self.player
        offset = menu.current_page * self.per_page

        looping = ""
        if player.looping_queue:
            looping = "(:repeat: Looping)"

        em = discord.Embed(title=f"Queue {looping}", description="", color=0x66FFCC)
        queue = ""
        for i, song in enumerate(entries, start=offset):
            queue += f"\n{i+1}. [{song.title}]({song.url}) `{song.duration}` - {song.requester.mention}"

        em.description = queue
        total_duration = 0
        for song in player.queue:
            total_duration+=song.total_seconds

        em.description += f"\n\n{Song.parse_duration(total_duration)} total"
        em.set_footer(text=f"{len(list(self.player.queue))} songs | Page {menu.current_page+1}/{(int(len(list(self.player.queue))/10))+1}")  

        return em

class Player:
    __slots__ = ("ctx", "voice", "queue", "_event",
                 "now", "notifications", "looping", "looping_queue", "_volume",
                 "song_started", "pause_started", "loop")

    def __init__(self, ctx, voice):
        self.ctx = ctx
        self.voice = voice
        self.queue = Queue(loop=self.bot.loop)
        self._event = asyncio.Event(loop=self.bot.loop)

        self.now = None
        self.notifications = True
        self.looping = False
        self.looping_queue = False
        self._volume = .5

        self.song_started = None
        self.pause_started = None
        self.loop = self.bot.loop.create_task(self.player_loop())

    def __str__(self):
        return f"channel ID {self.channel.id} (guild ID {self.guild.id})"

    @property
    def bot(self):
        return self.ctx.bot

    @property
    def guild(self):
        return self.voice.guild

    @property
    def channel(self):
        return self.voice.channel

    @property
    def latency(self):
        return self.voice.latency

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        if self.source:
            self.source.volume = value

    @property
    def source(self):
        return self.voice.source

    @source.setter
    def source(self, value):
        self.voice.source = value

    @property
    def is_playing(self):
        if self.now:
            return True
        else:
            return False

    @property
    def duration(self):
        if self.pause_started:
            return (time.time()-self.song_started) - (time.time()-self.pause_started)
        return (time.time()-self.song_started)

    @property
    def bar(self):
        bar = ""
        decimal = self.duration/self.now.total_seconds

        i = int(decimal*30)
        for x in range(30):
            if x == i:
                bar += "🔘"
            else:
                bar += "▬"
        return bar

    @property
    def embed(self):
        playing = ":pause_button:" if self.voice.is_playing() else ":arrow_forward:"
        looping = ":repeat:" if self.looping else ""

        em = discord.Embed(title=f"{playing}{looping} {self.now.title}", color=0x66FFCC)
        em.set_thumbnail(url=self.now.thumbnail)
        em.add_field(name="Duration", value=f"{Song.parse_timestamp_duration(self.duration)}/{self.now.timestamp_duration} `{self.bar}`", inline=False)
        em.add_field(name="Url", value=f"[Click]({self.now.url})")
        em.add_field(name="Uploader", value=f"[{self.now.uploader}]({self.now.uploader_url})")
        em.add_field(name="Requester", value=f"{self.now.requester.mention}")
        return em

    async def player_loop(self):
        log.info("Starting player loop for %s", self)
        try:
            while True:
                # Wait for new song (if needed)
                if not self.now:
                    log.info("Getting a song from the queue for %s", self)
                    try:
                        self.now = await asyncio.wait_for(self.queue.get(), timeout=180, loop=self.bot.loop)
                    except asyncio.TimeoutError:
                        log.info("Timed out while getting song from queue for %s. Cleaning up player.", self)
                        self.stop()
                        await self.voice.disconnect()
                        if self.guild.id in self.bot.players:
                            self.bot.players.pop(self.guild.id)
                        return

                if not self.voice.is_connected():
                    # We aren't connected, so wait until we are
                    log.info("Waiting until we are connected to play music in %s", self)
                    await self.bot.loop.run_in_executor(None, self.voice._connected.wait)

                log.info("Playing a song in %s", self)
                source = self.now.source(self.volume)
                self.voice.play(source, after=self.after_song)
                self.song_started = time.time()

                query = """UPDATE songs
                           SET plays = plays + 1
                           WHERE songs.id=$1;
                        """
                await self.ctx.bot.db.execute(query, self.now.id)

                if self.notifications:
                    await self.ctx.send(f":notes: Now playing `{self.now.title}`")

                # Wait till the song is over and then resume the loop
                log.info("Waiting for song to finish in %s", self)
                await self._event.wait()
                log.info("Song has finished in %s", self)
                self._event.clear()
                self.song_started = None
                self.pause_started = None

                if self.looping_queue and not self.looping:
                    await self.queue.put(self.now)
                if not self.looping:
                    self.now = None

        except Exception as exc:
            log.error("Exception in player loop for %s. Shutting down player.", self, exc_info=exc)

            if self.queue:
                url = await self.save_queue(player)
                await self.ctx.send(f"Sorry! Your player has crashed. If your confused or want to report this, join <{bot.support_server_link}>. You can start again with `{ctx.prefix}playbin {url}`.")
            elif self.now:
                await self.ctx.send(f"Sorry! Your player has crashed. If your confused or want to report this, join <{bot.support_server_link}>. You can start your song again with the play command.")

            log.info("Stopping music for %s", self)
            self.stop()
            log.info("Disconnecting from %s", self)
            await self.voice.disconnect()
            log.info("Deleting player for %s", self)
            if self.guild.id in self.bot.players:
                self.bot.players.pop(self.guild.id)
            return

    def after_song(self, exc):
        if not exc:
            self._event.set()
        else:
            log.error("Exception in after function for %s", self, exc_info=exc)

    async def update_voice(self, channel):
        await self.guild.change_voice_state(channel=channel)

    def pause(self):
        if self.pause_started and self.song_started:
            self.song_started += (time.time()-self.pause_started)
            self.pause_started = None

        self.voice.pause()
        self.pause_started = time.time()

    def resume(self):
        if self.pause_started and self.song_started:
            self.song_started += (time.time()-self.pause_started)
            self.pause_started = None

        self.voice.resume()

    def skip(self):
        self.voice.stop()

    def stop(self):
        self.queue.clear()
        self.voice.stop()
        self.now = None

    async def cleanup(self):
        log.info("Canceling player loop for %s", self)
        self.loop.cancel()
        log.info("Stopping music for %s", self)
        self.stop()
        log.info("Disconnecting from %s", self)
        await self.voice.disconnect()
        log.info("Deleting player for %s", self)
        if self.guild.id in self.bot.players:
            self.bot.players.pop(self.guild.id)

    async def save_queue(self, player):
        queue = [song.url for song in player.queue]
        if player.looping_queue:
            queue = [player.now.url] + queue
        return await self.bot.post_bin("\n".join(queue))

class Song:
    __slots__ = ("_data", "filename", "requester", "song_id", "extractor",
                 "uploader", "uploader_url", "date", "total_seconds", "upload_date",
                 "title", "thumbnail", "description", "duration", "timestamp_duration",
                 "tags", "url", "views", "likes", "dislikes",
                 "stream_url", "id", "plays", "created_at",
                 "updated_at")

    FFMPEG_OPTIONS = {
        "options": "-vn"
    }

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

    def __init__(self, ctx, *, data, filename=None):
        self._data = data
        self.filename = filename
        self.requester = ctx.author

        self.song_id = data.get("id")
        self.extractor = data.get("extractor")
        self.uploader = data.get("uploader")
        self.uploader_url = data.get("uploader_url")
        self.date = data.get("upload_date")
        self.total_seconds = int(data.get("duration") or 0)
        self.upload_date = self.date[6:8] + "." + self.date[4:6] + "." + self.date[0:4] if self.date else None
        self.title = data.get("title")
        self.thumbnail = data.get("thumbnail")
        self.description = data.get("description")
        self.duration = self.parse_duration(self.total_seconds)
        self.timestamp_duration = self.parse_timestamp_duration(self.total_seconds)
        self.tags = data.get("tags")
        self.url = data.get("webpage_url")
        self.views = data.get("view_count")
        self.likes = data.get("like_count")
        self.dislikes = data.get("dislike_count")
        self.stream_url = data.get("url")

        self.id = None
        self.plays = None
        self.created_at = None
        self.updated_at = None

    def source(self, volume, **options):
        options = {**self.FFMPEG_OPTIONS, **options}
        source = discord.FFmpegPCMAudio(self.filename, **options)
        transformed = discord.PCMVolumeTransformer(source, volume)
        return transformed

    @property
    def embed(self):
        em = discord.Embed(title=self.title, color=0x66FFCC)
        em.set_thumbnail(url=self.thumbnail)
        em.add_field(name="Duration", value=str(self.timestamp_duration))
        em.add_field(name="Url", value=f"[Click]({self.url})")
        em.add_field(name="Uploader", value=f"[{self.uploader}]({self.uploader_url})")
        em.add_field(name="Requester", value=f"{self.requester.mention}")
        return em

    @classmethod
    async def from_query(cls, ctx, search):
        # Check if the search and result is already cached in the database
        possible_song = await cls.from_alias(ctx, search)
        if possible_song:
            return possible_song

        # This checks to see if the query is a youtube song name or id that is already cached in the database and returns the result if any is found
        youtube_id = cls.parse_youtube_id(search) or search
        query = """SELECT *
                   FROM songs
                   WHERE (songs.title=$1 OR songs.song_id=$2) AND songs.extractor='youtube';
                """
        record = await ctx.bot.db.fetchrow(query, search, youtube_id)
        if record:
            await cls.create_alias(ctx, search, record["id"])
            return cls.from_record(record, ctx)

        # Resolve the query into a full Song, so we can search the database
        song = await cls.resolve_query(ctx, search)
        query = """SELECT *
                   FROM songs
                   WHERE (songs.title=$1 OR songs.song_id=$2) AND songs.extractor=$3;
                """
        record = await ctx.bot.db.fetchrow(query, song.title, song.id, song.extractor)
        if record:
            await cls.create_alias(ctx, search, record["id"])
            return cls.from_record(record, ctx)

        # We shouldn't get here unless the song isn't in the database
        song = await cls.download_song(ctx, song)
        data = song._data

        # Cache the song and search in the database
        query = """INSERT INTO songs (song_id, title, filename, extractor, plays, data)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   RETURNING id;
                """
        value = await ctx.bot.db.fetchval(query, song.song_id, song.title, song.filename, song.extractor, 0, data)
        await cls.create_alias(ctx, search, value)

        return cls(ctx, data=data, filename=song.filename)

    @classmethod
    async def resolve_query(cls, ctx, search):
        partial = functools.partial(cls.ytdl.extract_info, search, download=False)
        try:
            info = await ctx.bot.loop.run_in_executor(None, partial)
        except youtube_dl.DownloadError as exc:
            raise errors.SongError(str(exc)) from exc

        if not info:
            raise errors.SongError(f"I couldn't resolve `{search}`")
        if "entries" in info:
            entries = info["entries"]
            if not entries:
                raise errors.SongError(f"I Couldn't find any results for `{search}`")
            info = entries[0]
        return cls(ctx, data=info, filename=cls.ytdl.prepare_filename(info))

    @classmethod
    async def download_song(cls, ctx, song):
        try:
            partial = functools.partial(cls.ytdl.extract_info, song.url)
            info = await asyncio.wait_for(ctx.bot.loop.run_in_executor(None, partial), timeout=180, loop=ctx.bot.loop)
        except youtube_dl.DownloadError as exc:
            raise errors.SongError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise errors.SongError(f"It took too long to download `{song.url}") from exc

        if not info:
            raise errors.SongError(f"I Couldn't download `{song.url}`")
        if "entries" in info:
            entries = info["entries"]
            if not entries:
                raise errors.SongError(f"I Couldn't find any results for `{search}`")
            info = entries[0]
        return cls(ctx, data=info, filename=cls.ytdl.prepare_filename(info))

    @classmethod
    async def from_database(cls, ctx, search):
        # Attempt to search for the song
        query = """SELECT *
                   FROM songs
                   WHERE songs.title % $1
                   ORDER BY similarity(songs.title, $1) DESC
                   LIMIT 1;
                """
        record = await ctx.bot.db.fetchrow(query, search)
        if record:
            return cls.from_record(record, ctx)

        # We need to find a song from the database by searching
        # First check if the song is an ID from the database
        query = """SELECT *
                   FROM songs
                   WHERE songs.id=$1;
                """
        if search.isdigit():
            int_search = int(search)
            record = await ctx.bot.db.fetchrow(query, int_search)
            if record:
                return cls.from_record(record, ctx)

        # Attempt to get the song by youtube ID
        query = """SELECT *
                   FROM songs
                   WHERE songs.song_id=$1;
                """
        record = await ctx.bot.db.fetchrow(query, search)
        if record:
            return cls.from_record(record, ctx)

        raise errors.SongError(f"I couldn't find any results for `{search}` in the database")

    @classmethod
    async def create_alias(cls, ctx, search, song_id):
        query = """INSERT INTO song_searches (search, song_id, expires_at)
                   VALUES ($1, $2, $3);
                """
        await ctx.bot.db.execute(query, search, song_id, datetime.datetime.utcnow()+datetime.timedelta(days=30))

    @classmethod
    async def from_alias(cls, ctx, search):
        query = """SELECT *
                   FROM song_searches
                   INNER JOIN songs ON song_searches.song_id=songs.id
                   WHERE song_searches.search=$1;
                """
        record = await ctx.bot.db.fetchrow(query, search)
        if record:
            if datetime.datetime.utcnow() < record["expires_at"]:
                return cls.from_record(record, ctx)
            else:
                await cls.delete_alias(ctx, search)

    @classmethod
    async def delete_alias(cls, ctx, search):
        query = """DELETE FROM song_searches
                   WHERE song_searches.search=$1;
                """
        await ctx.bot.db.execute(query, search)

    @classmethod
    async def playlist(cls, ctx, search, *, download=True):
        # Extract the songs
        partial = functools.partial(cls.ytdl.extract_info, search, download=download)
        try:
            info = await asyncio.wait_for(ctx.bot.loop.run_in_executor(None, partial), timeout=180, loop=ctx.bot.loop)
        except youtube_dl.DownloadError as exc:
            raise errors.SongError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise errors.SongError("It took to long to download that playlist")
        if not info:
            raise errors.SongError(f"Couldn't find anything that matches `{search}`")
        if "entries" not in info:
            raise errors.SongError(f"No entries for `{search}`")

        # Turn each item into a song
        songs = []
        for data in info["entries"]:
            song = Song(ctx, data=data, filename=cls.ytdl.prepare_filename(data))
            songs.append(song)

        if not songs:
            raise errors.SongError("Playlist is empty")
        return songs

    @classmethod
    def from_record(cls, record, ctx):
        self = cls(ctx, data=record["data"], filename=record["filename"])

        self.id = record["id"]
        self.plays = record["plays"]
        self.created_at = record["created_at"]
        self.updated_at = record["updated_at"]

        return self

    @staticmethod
    def parse_youtube_id(url):
        regex = re.compile("(?:https?://)?(?:www.)?(?:youtube.com|youtu.be)/(?:watch\\?v=)?([^\\s]+)")
        youtube_id = regex.findall(url)
        return youtube_id[0] if youtube_id else None

    @staticmethod
    def parse_duration(duration):
        duration = int(duration)

        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration_str = []
        if days > 0:
            duration_str.append(f"{formats.plural(days):day}")
        if hours > 0:
            duration_str.append(f"{formats.plural(hours):hour}")
        if minutes > 0:
            duration_str.append(f"{formats.plural(minutes):minute}")
        if seconds > 0:
            duration_str.append(f"{formats.plural(seconds):second}")

        return ", ".join(duration_str)

    @staticmethod
    def parse_timestamp_duration(duration):
        duration = int(duration)

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

class Queue(asyncio.Queue):
    def __getitem__(self, key):
        if isinstance(key, slice):
            return list(itertools.islice(self._queue, key.start, key.stop, key.step))
        else:
            return self._queue[key]

    def __setitem__(self, key, value):
        self._queue[key] = value

    def __delitem__(self, key, value):
        del self._queue[key]

    def __iter__(self):
        return self._queue.__iter__()

    def __reversed__(self):
        return reversed(self._queue)

    def __contains__(self, item):
        return item in self._queue

    def __len__(self):
        return self.qsize()

    def __bool__(self):
        return self._queue.__bool__()

    def remove(self, item):
        self._queue.remove(item)

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

class PositionConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            position = human_time.ShortTime(arg, now=ctx.message.created_at)
            delta = position.time-ctx.message.created_at
            return delta.total_seconds()
        except commands.BadArgument:
            pass

        if ":" not in arg:
            try:
                return int(arg)
            except ValueError as exc:
                raise commands.BadArgument("Song position is not an integer")

        args = arg.split(":")
        if len(args) > 3:
            raise commands.BadArgument("Song position timestamp is invalid")

        position = 0
        times = [1, 60, 1440]
        for counter, arg in enumerate(reversed(args)):
            try:
                arg = int(arg)
                position += arg * times[counter]
            except ValueError:
                raise commands.BadArgument(f"`{arg}` is not an integer")

        return position

class PossibleURL(commands.Converter):
    async def convert(self, ctx, arg):
        return arg.strip("<>")

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":notes:"

    def cog_check(self, ctx):
        return ctx.guild

    @commands.command(name="connect", description="Connect the bot to a voice channel", aliases=["join"])
    async def connect(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send(":x: You are not connected to a voice channel")

        if not ctx.author.voice:
            return await ctx.send("You are not in any voice channel")
        elif ctx.guild.id in self.bot.players or ctx.voice_client:
            return await ctx.send("Already connected to a voice channel")
        elif not channel.permissions_for(ctx.me).connect:
            return await ctx.send(f":x: I don't have permissions to connect to `{channel}`")
        elif channel.user_limit and len(channel.members) >= channel.user_limit and not ctx.me.guild_permissions.move_members:
            return await ctx.send(f"I can't connect to `{channel}` because it's full")

        log.info("Attempting to connect to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)
        try:
            voice_client = await channel.connect()
        except:
            log.info("Failed to connect to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)
            if ctx.guild.id in self.bot.players:
                return
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            return await ctx.send(f"I couldn't connect to `{channel}`")

        self.bot.players[ctx.guild.id] = Player(ctx, voice_client)
        player = self.bot.players[ctx.guild.id]

        if isinstance(channel, discord.StageChannel):
            log.info("Attempting to become a speaker")

            try:
                await ctx.me.edit(suppress=False)
                log.info("Successfully became a speaker")
            except discord.Forbidden:
                log.warning("In-sufficient permissions to become a speaker. Requesting to speak instead.")
                await ctx.me.request_to_speak()

                return await ctx.send(f"Connected to `{channel}` ")

        await ctx.send(f"Connected to `{channel}`")
        log.info("Successfully connected to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)
        return player

    @commands.command(name="summon", description="Summon the bot to a different channel")
    async def summon(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send(":x: You are not connected to a voice channel")

        if not channel.permissions_for(ctx.me).connect:
            await ctx.send(f"I don't have permissions to connect to `{channel}`")
        elif channel.user_limit and len(channel.members) >= channel.user_limit and not ctx.me.guild_permissions.move_members:
            await ctx.send(f"I can't connect to `{channel}` because it's full")

        log.info("Moving player in %s to channel ID %s", ctx.player, channel.id)
        await ctx.player.update_voice(channel)

        def check(member, before, after):
            player = self.bot.players[ctx.guild.id]

            if not player:
                return False
            elif member != ctx.me or after.channel != channel:
                return False
            else:
                return True

        # Prevent from un-supressing to soon and getting errors
        await self.bot.wait_for("voice_state_update", timeout=10, check=check)

        log.info("Successfully moved player to %s", ctx.player)
        ctx.player.ctx = ctx

        if isinstance(channel, discord.StageChannel):
            log.info("Attempting to become a speaker")

            try:
                await ctx.me.edit(suppress=False)
                log.info("Successfully became a speaker")
            except discord.Forbidden:
                log.warning("In-sufficient permissions to become a speaker. Requesting to speak instead.")
                await ctx.me.request_to_speak()

                return await ctx.send(f"Connected to `{channel}` ")

        await ctx.send(f"Now connected to `{channel}` and bound to `{ctx.channel}`")

    @commands.command(name="play", description="Play a song", aliases=["p"])
    async def play(self, ctx, *, query: PossibleURL):
        if ctx.author not in ctx.player.channel.members:
            return

        await ctx.send(f":mag: Searching for `{query}`")

        if "list=" in query:
            await ctx.send(":globe_with_meridians: Downloading playlist")

            async with ctx.typing():
                songs = await Song.playlist(ctx, query)
                for song in songs:
                    await ctx.player.queue.put(song)

            await ctx.send(f":white_check_mark: Finished downloading playlist")
        else:
            async with ctx.typing():
                song = await Song.from_query(ctx, query)

            if ctx.player.is_playing:
                await ctx.send(f":page_facing_up: Enqueued `{song.title}`")
            elif not ctx.player.notifications:
                await ctx.send(f":notes: Now playing `{song.title}`")

            await ctx.player.queue.put(song)

    @commands.command(name="playbin", description="Play a list of songs", aliases=["pb"])
    async def playbin(self, ctx, url: PossibleURL):
        if ctx.author not in ctx.player.channel.members:
            return

        await ctx.send(":globe_with_meridians: Downloading bin")

        async with ctx.typing():
            try:
                songs = await self.get_bin(url=url)
            except:
                return await ctx.send(":x: I couldn't fetch that bin. Make sure the URL is valid.")
            for url in songs:
                song = await Song.from_query(ctx, url)
                await ctx.player.queue.put(song)

        await ctx.send(f":white_check_mark: Finished downloading bin")

    @commands.command(name="search", description="Search for a song on youtube")
    async def search(self, ctx, *, query):
        if ctx.author not in ctx.player.channel.members:
            return

        async with ctx.typing():
            songs = await Song.playlist(ctx, f"ytsearch5:{query}", download=False)

        pages = SongSelectorMenuPages(songs, clear_reactions_after=True)
        song = await pages.prompt(ctx)

        if not song:
            return await ctx.send("Aborting")

        song = await Song.from_query(ctx, song.url)

        if ctx.player.is_playing:
            await ctx.send(f":page_facing_up: Enqueued `{song.title}`")
        elif not ctx.player.notifications:
            await ctx.send(f":notes: Now playing `{song.title}`")

        await ctx.player.queue.put(song)

    @commands.command(name="pause", description="Pause the music")
    async def pause(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now or ctx.player.voice.is_paused():
            return

        ctx.player.pause()
        await ctx.send(":arrow_forward: Paused")

    @commands.command(name="resume", description="Resume the music")
    async def resume(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now or ctx.player.voice.is_playing():
            return

        ctx.player.resume()
        await ctx.send(":pause_button: Resumed")

    @commands.command(name="startover", description="Start the current song from the beginning")
    async def startover(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now:
            return

        ctx.player.source = ctx.player.now.source(ctx.player.volume)
        ctx.player.song_started = time.time()
        ctx.player.pause_started = None

        await ctx.send(":rewind: Starting over")

    @commands.command(name="skip", description="Skip the music")
    async def skip(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now:
            return

        ctx.player.skip()
        await ctx.send(":track_next: Skipped current song")

    @commands.command(name="skipto", description="Jump to a song in the queue")
    async def skipto(self, ctx, position: int):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now:
            return

        if position == 0 or position > len(ctx.player.queue):
            return await ctx.send(":x: That is not a song in the queue")

        position = position - 1

        # Remove all the song (and add them back to the end if looping) until we reach the song we want to skip to
        for x in range(position):
            current = await ctx.player.queue.get()
            if ctx.player.looping_queue:
                await ctx.player.queue.put(current)

        ctx.player.skip()
        song = ctx.player.queue[0]
        await ctx.send(f":track_next: Jumped to `{song.title}`")

    @commands.command(name="seek", description="Seek a position in the song")
    async def seek(self, ctx, *, position: PositionConverter):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.now:
            return

        if position > ctx.player.now.total_seconds or position < 0:
            return await ctx.send(":x: That is not a valid position")
        emoji = ":fast_forward:" if position >= ctx.player.duration else ":rewind:"

        # Remake the source using the -ss option
        timestamp = Song.parse_timestamp_duration(position)
        ctx.player.source = ctx.player.now.source(ctx.player.volume, before_options=f"-ss {timestamp}")

        ctx.player.song_started = time.time()-position
        ctx.player.pause_started = None

        await ctx.send(f"{emoji} Seeked `{timestamp}`")

    @commands.group(name="loop", description="Loop the song", aliases=["repeat"], invoke_without_command=True)
    async def loop(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return

        if ctx.player.looping:
            ctx.player.looping = False
            await ctx.send(":x::repeat_one: Unlooped song")
        else:
            ctx.player.looping = True
            await ctx.send(":repeat_one: Looped song")

    @loop.command(name="queue", description="Loop the queue")
    async def loop_queue(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return

        if ctx.player.looping_queue:
            ctx.player.looping_queue = False
            await ctx.send(":x::repeat: Not looping queue")
        else:
            ctx.player.looping_queue = True
            await ctx.send(":repeat: Looping queue")

    @commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return

        ctx.player.queue.shuffle()
        await ctx.send(":twisted_rightwards_arrows: Shuffled music")

    @commands.command(name="volume", description="Set the volume")
    async def volume(self, ctx, volume: int = None):
        if ctx.author not in ctx.player.channel.members:
            return

        if volume is None:
            emoji = ":loud_sound:" if ctx.player.volume >= 50 else ":sound:"
            return await ctx.send(f"{emoji} `{int(ctx.player.volume * 100)}%`")
        if volume < 0 or volume > 100:
            return await ctx.send(":x: Volume must be between 0 and 100")

        ctx.player.volume = volume / 100
        await ctx.send(f":loud_sound: Volume set to `{volume}%`")

    @commands.command(name="notify", description="Toggle now playing messages")
    async def notify(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return

        if ctx.player.notifications:
            ctx.player.notifications = False
            await ctx.send(":no_bell: Notifications disabled")
        else:
            ctx.player.notifications = True
            await ctx.send(":bell: Notifications enabled")

    @commands.command(name="stop", description="Stop the music")
    async def stop(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return

        ctx.player.stop()
        await ctx.send(":stop_button: Stopped music and cleared queue")

    @commands.command(name="now", description="Get the current playing song", aliases=["np"])
    async def now(self, ctx):
        if not ctx.player.now:
            return await ctx.send("Not playing anything")

        await ctx.send(embed=ctx.player.embed)

    @commands.command(name="next", description="View the next song in the queue", aliases=["nextup"])
    async def next(self, ctx):
        if not ctx.player.queue:
            return await ctx.send(":x: The queue is empty")

        song = ctx.player.queue[0]
        await ctx.send(embed=song.embed)

    @commands.group(name="queue", description="View the queue", invoke_without_command=True)
    async def queue(self, ctx, position: int = None):
        if not ctx.player.queue:
            return await ctx.send("The queue is empty")

        if not position:
            pages = menus.MenuPages(source=QueuePages(ctx.player), clear_reactions_after=True)
            await pages.start(ctx)
        else:
            if position == 0 or position > len(ctx.player.queue):
                return await ctx.send("That is not a song in the queue")
            song = ctx.player.queue[position-1]
            await ctx.send(embed=song.embed)

    @queue.command(name="save", description="Save the queue")
    async def queue_save(self, ctx):
        if ctx.player.queue:
            url = await ctx.playersave_queue(ctx.player)
            await ctx.send(f"I saved the queue to {url}")
        else:
            await ctx.send("No queue to save")

    @queue.command(name="remove", description="Remove a song from the queue")
    async def queue_remove(self, ctx, position: int):
        if ctx.author not in ctx.player.channel.members:
            return
        if position == 0 or position > len(ctx.player.queue):
            return await ctx.send(":x: That is not a song in the queue")

        song = ctx.player.queue[position-1]
        ctx.player.queue.remove(song)
        await ctx.send(f":wastebasket: Removed `{song.title}` from queue")

    @queue.command(name="clear", description="Clear the queue")
    async def queue_clear(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return
        if not ctx.player.queue:
            return await ctx.send(":x: Queue is empty")

        ctx.player.queue.clear()
        await ctx.send(":wastebasket: Cleared queue")

    @commands.command(name="disconnect", description="Disconnect the bot from a voice channel", aliases=["leave"])
    async def disconnect(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        # We have a player so we can disconnect normally
        if player:
            channel = player.channel
            if ctx.author not in player.channel.members:
                return

            log.info("Disconnecting from %s normally", player)

            if player.queue:
                url = await player.save_queue(player)
                await ctx.send(f"I saved the queue to {url}")

            await player.cleanup()
            await ctx.send(f"Disconnected from `{channel}`")
            log.info("Disconnected from %s normally", player)

        # Somehow discord.py have a voice client, but we don't have a player so we can disconnect the voice client and cleanup if needed
        elif ctx.voice_client:
            channel = ctx.voice_client.channel
            log.warning("Disconnecting from channel ID %s (guild ID %s) forcefully", channel.id, ctx.guild.id)

            await ctx.voice_client.disconnect()
            if ctx.guild.id in self.bot._connection._voice_clients:
                log.warning("Removing voice connection to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)
                self.bot._connection._voice_clients.pop(ctx.guild.id)
            await ctx.send(f"Disconnected from `{channel}`")
            log.warning("Disconnected from channel ID %s (guild ID %s) forcefully", channel.id, ctx.guild.id)

    @commands.group(name="songs", description="View some stats about music", invoke_without_command=True, aliases=["song"])
    @commands.is_owner()
    async def songs(self, ctx):
        query = """SELECT *
                   FROM songs;
                """
        songs = await self.bot.db.fetch(query)
        songs = [Song.from_record(song, ctx) for song in songs]

        song_count = len(songs)
        play_count = sum([song.plays for song in songs])
        music_legnth = sum([song.total_seconds for song in songs])
        music_played = sum([song.total_seconds*song.plays for song in songs])
        music_cache_size = sum([os.path.getsize(song.filename) for song in songs])

        em = discord.Embed(title="Music Stats", color=0x96c8da)
        em.add_field(name="Song Count", value=song_count)
        em.add_field(name="Play Count", value=play_count)
        em.add_field(name="Music Cache Size", value=humanize.naturalsize(music_cache_size, binary=True))
        em.add_field(name="Music Legnth", value=Song.parse_duration(music_legnth))
        em.add_field(name="Music Played", value=Song.parse_duration(music_played))
        await ctx.send(embed=em)

    @songs.command(name="list", description="List all the songs in the database")
    @commands.is_owner()
    async def song_list(self, ctx):
        query = """SELECT *
                   FROM songs;
                """
        songs = await self.bot.db.fetch(query)
        songs = [Song.from_record(song, ctx) for song in songs]

        if not songs:
            return await ctx.send(f":x: I don't have any songs in my database")

        songs ="\n".join([f"[{song.id}] {song.title} # {song.song_id} ({song.extractor}) | {song.plays} plays | last updated {humanize.naturaldelta(song.updated_at-datetime.datetime.utcnow())} ago" for song in songs])
        await ctx.send(f"```ini\n{songs}\n```")

    @songs.command(name="search", description="Search for a song in the database")
    @commands.is_owner()
    async def song_search(self, ctx, *, search):
        query = """SELECT *
                   FROM songs
                   WHERE songs.title % $1
                   ORDER BY similarity(songs.title, $1) DESC
                   LIMIT 10;
                """
        songs = await self.bot.db.fetch(query, search)
        songs = [Song.from_record(song, ctx) for song in songs]

        if not songs:
            return await ctx.send(f":x: I couldn't find any songs in the database that matched `{search}`")

        songs ="\n".join([f"[{song.id}] {song.title} # {song.song_id} ({song.extractor}) | {song.plays} plays | last updated {humanize.naturaldelta(song.updated_at-datetime.datetime.utcnow())} ago" for song in songs])
        await ctx.send(f"```ini\n{songs}\n```")

    @songs.command(name="info", description="Get info on a song")
    @commands.is_owner()
    async def song_info(self, ctx, *, song):
        song = await Song.from_database(ctx, song)

        em = discord.Embed(title=song.title, timestamp=song.updated_at, color=0x66FFCC)
        em.set_thumbnail(url=song.thumbnail)
        em.add_field(name="Duration", value=str(song.timestamp_duration))
        em.add_field(name="Url", value=f"[Click]({song.url})")
        em.add_field(name="Uploader", value=f"[{song.uploader}]({song.uploader_url})")
        em.add_field(name="Song ID", value=song.song_id)
        em.add_field(name="Extractor", value=song.extractor)
        em.add_field(name="Size", value=humanize.naturalsize(os.path.getsize(song.filename), binary=True))
        em.add_field(name="Filename", value=discord.utils.escape_markdown(song.filename))
        em.add_field(name="Plays", value=song.plays)
        em.add_field(name="ID", value=song.id)
        em.set_footer(text="Updated")
        await ctx.send(embed=em)

    @songs.command(name="update", description="Update a song in the database", aliases=["refresh"])
    @commands.is_owner()
    async def song_update(self, ctx, *, song):
        song = await Song.from_database(ctx, song)
        song_id = song.id

        async with ctx.typing():
            # Resolve the song info, then download the song
            song = await Song.resolve_query(ctx, song.url)
            song = await Song.download_song(ctx, song)
            query = """UPDATE songs
                       SET title=$1, filename=$2, data=$3, updated_at=$4
                       WHERE songs.id=$5;
                    """
            await self.bot.db.execute(query, song.title, song.filename, song._data, datetime.datetime.utcnow(), song_id)

        await ctx.send(f":white_check_mark: `{song.title}` has been updated")

    @songs.command(name="delete", description="Delete a song from the database", aliases=["remove"])
    @commands.is_owner()
    async def song_delete(self, ctx, *, song):
        song = await Song.from_database(ctx, song)

        query = """DELETE FROM songs
                   WHERE songs.id=$1;
                """
        await self.bot.db.execute(query, song.id)
        await ctx.send(f":white_check_mark: `{song.title}` has been deleted")

    @commands.command(name="allplayers", description="View all players")
    @commands.is_owner()
    async def allplayers(self, ctx):
        if not self.bot.players:
            return await ctx.send("No players")

        players = []
        for player in self.bot.players.values():
            info = f"{player.guild} - `{player.channel} | {player.ctx.channel}`"
            latency = f"{player.latency*1000:.2f}ms"
            players.append(f"{info} ({latency})")

        await ctx.send("\n".join(players))

    @commands.command(name="stopall", description="Stop all players")
    @commands.is_owner()
    async def stopall(self, ctx):
        await self.bot.stop_players()
        await ctx.send("All players have been stopped")
        log.info("Stopped all players")

    @commands.Cog.listener("on_voice_state_update")
    async def disconnect_on_inactivity(self, member, before, after):
        player = self.bot.players.get(member.guild.id)
        if not player or member.bot:
            return

        # If the voice channel is empty, pause and wait for someone to join
        members = [member for member in player.channel.members if not member.bot]
        if members:
            return
        paused = player.voice.is_paused()
        player.pause()
        log.info("%s is empty. Waiting for someone to join.", player)

        try:
            check = lambda member, before, after: (not member.bot and after.channel and after.channel == player.channel) or (member.id == self.bot.user.id and after.channel and after.channel != before.channel)
            await self.bot.wait_for("voice_state_update", timeout=180, check=check)
            log.info("Someone joined %s. Continuing player.", player)
            # Someone joined so we can resume if we paused on disconnect
            if not paused:
                player.resume()

        except asyncio.TimeoutError:
            log.info("Timed out while waiting for someone to join %s", player)
            # If the voice channel is empty for 3 minutes then disconnect
            if player.queue:
                url = await player.save_queue(player)
                await player.ctx.send(f"I left `{player.voice.channel}` because it was empty. The queue has been saved to {url}.")
            await player.cleanup()

    @commands.Cog.listener("on_voice_state_update")
    async def cleanup_on_disconnect(self, member, before, after):
        player = self.bot.players.get(member.guild.id)
        if not player:
            return
        if member.id != self.bot.user.id or not before.channel or after.channel:
            return

        log.info("Unexpectedly disconnected from %s. Waiting to rejoin.", player)

        # Wait for the player to reconnect
        try:
            def check(member, before, after):
                player = self.bot.players[member.guild.id]

                if not player:
                    return False
                elif member.id != self.bot.user.id or after.channel:
                    return False
                else:
                    return True

            await self.bot.wait_for("voice_state_update", timeout=10, check=check)
            log.info("Successfully rejoined %s", player)
        except asyncio.TimeoutError:
            # Cleanup the player since we didn't reconnect
            log.info("Didn't rejoin %s. Cleaning up player.", player)
            if player.queue:
                url = await player.save_queue(player)
                await player.ctx.send(f"I was disconnected from `{player.voice.channel}`! The queue has been saved to {url}.")
            await player.cleanup()

    @play.before_invoke
    @playbin.before_invoke
    @search.before_invoke
    async def create_player(self, ctx):
        if ctx.guild.id not in self.bot.players:
            log.info("Connecting to voice before invoking command")
            await self.connect(ctx)

            if ctx.guild.id not in self.bot.players:
                raise errors.VoiceError()

        ctx.player = self.bot.players[ctx.guild.id]

    @summon.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    @startover.before_invoke
    @skip.before_invoke
    @skipto.before_invoke
    @seek.before_invoke
    @loop.before_invoke
    @loop_queue.before_invoke
    @shuffle.before_invoke
    @volume.before_invoke
    @notify.before_invoke
    @stop.before_invoke
    @now.before_invoke
    @next.before_invoke
    @queue.before_invoke
    @queue_save.before_invoke
    @queue_remove.before_invoke
    @queue_clear.before_invoke
    async def get_player(self, ctx):
        player = self.bot.players.get(ctx.guild.id)
        if not player:
            raise errors.VoiceError("I am connected to any voice channel")
        ctx.player = player

    async def get_bin(self, url):
        parsed = urllib.parse.urlparse(url)
        newpath = "/raw" + parsed.path
        url = parsed.scheme + "://" + parsed.netloc + newpath
        async with self.bot.session.get(url) as response:
            data = await response.read()
            data = data.decode("utf-8")
            return data.split("\n")

def setup(bot):
    bot.add_cog(Music(bot))
