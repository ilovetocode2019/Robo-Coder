import asyncio
import datetime
import functools
import io
import itertools
import logging
import os
import random
import re
import time
import typing
import urllib

import discord
import humanize
import yt_dlp
from discord.ext import commands, menus

from .utils import errors, formats, human_time, spotify

log = logging.getLogger("robo_coder.music")

class SongSelectorView(discord.ui.View):
    def __init__(self, ctx, songs):
        super().__init__()
        self.ctx = ctx
        self.songs = songs

        self.current_page = 0

    @discord.ui.button(label="Play", style=discord.ButtonStyle.success)
    async def play(self, interaction, button):
        await interaction.response.defer()

        song = await Song.confirm_download(self.ctx, self.songs[self.current_page], extract_info=False)

        if self.ctx.player.is_playing:
            await interaction.followup.send(f":page_facing_up: Enqueued `{song.title}`")
        elif self.ctx.interaction:
            song.interaction = self.ctx.interaction

        await self.ctx.player.queue.put(song)

        self.disable_buttons()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous(self, interaction, button):
        if self.current_page == 0:
            return await interaction.response.defer()

        self.current_page -= 1
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_(self, interaction, button):
        if self.current_page == len(self.songs) - 1:
            return await interaction.response.defer()

        self.current_page += 1
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        self.disable_buttons()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        self.disable_buttons()
        await self.message.edit(view=self)

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    @property
    def embed(self):
        song = self.songs[self.current_page]

        em = discord.Embed(title=song.title, color=0x66FFCC)
        em.set_thumbnail(url=song.thumbnail)
        em.add_field(name="Duration", value=f"{song.timestamp_duration}")
        em.add_field(name="Url", value=f"[Click]({song.url})")
        em.add_field(name="Uploader", value=f"[{song.uploader}]({song.uploader_url})")
        em.set_footer(text=f"{len(self.songs)} results | Page {self.current_page+1}/{len(self.songs)}")

        return em

class QueueBackButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(label="Previous Page", style=discord.ButtonStyle.primary)
        self.parent = parent

    async def callback(self, interaction):
        if self.parent.current_page == 0:
            return await interaction.response.defer()

        self.parent.current_page -= 1
        await interaction.response.edit_message(embed=self.parent.embed)

class QueueNextButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(label="Next Page", style=discord.ButtonStyle.primary)
        self.parent = parent

    async def callback(self, interaction):
        if self.parent.current_page == len(self.parent.pages) - 1:
            return await interaction.response.defer()

        self.parent.current_page += 1
        await interaction.response.edit_message(embed=self.parent.embed)

class QueueView(discord.ui.View):
    def __init__(self, player):
        super().__init__()

        self.per_page = 10
        self.current_page = 0
        self.pages = []

        for page in range(0, len(player.queue), self.per_page):
            self.pages.append(player.queue[page:page + self.per_page])

        self.queue_duration = Song.parse_duration(sum([song.total_seconds for song in player.queue]))
        self.queue_length = len(player.queue)
        self.is_looping = player.looping_queue

        if len(self.pages) > 1:
            self.add_item(QueueBackButton(self))
            self.add_item(QueueNextButton(self))

    @property
    def embed(self):
        songs = self.pages[self.current_page]
        offset = self.current_page * self.per_page

        em = discord.Embed(title=f"Queue {'(:repeat: Looping)' if self.is_looping else ''}", description="", color=0x66FFCC)

        for i, song in enumerate(songs, start=offset):
            em.description += f"\n{i+1}. [{song.title}]({song.url}) `{song.duration}` - {song.requester.mention}"

        em.description += f"\n\n{self.queue_duration} total"

        em.set_footer(text=f"{self.queue_length} songs | Page {self.current_page+1}/{(int(self.queue_length/10))+1}")  

        return em

class MusicVoiceClient(discord.VoiceClient):
    async def disconnect(self, force=False):
        await super().disconnect(force=force)
        player = self.client.players.get(self.guild.id)

        if player:
            log.info("VOICE CLIENT: Cleaning up left-over voice client in %s. This might be caused by a force disconnect.", player)
            await player.cleanup()

class MusicAudioSource(discord.FFmpegPCMAudio):
    def __init__(self, filename, *, speed=1, start=0):
        super().__init__(
            filename,
            before_options=f"-ss {start}" if start != 0 else None,
            options=f"-vn -filter:a atempo='{speed}'"  if speed != 1 else "-vn"
        )

        self.position = start * 1000

    def read(self):
        ret = super().read()

        if ret:
            self.position += discord.opus.Encoder.FRAME_LENGTH

        return ret

class MusicPlayer:
    __slots__ = ("voice", "text_channel", "queue", "_event", "now",
                 "notifications", "looping", "looping_queue",
                 "_volume", "_speed", "_is_skip", "loop")

    def __init__(self, voice, text_channel):
        self.voice = voice
        self.text_channel = text_channel

        self.queue = Queue()
        self._event = asyncio.Event()

        self.now = None
        self.notifications = True
        self.looping = False
        self.looping_queue = False

        self._volume = .5
        self._speed = 1
        self._is_skip = False

        self.loop = self.bot.loop.create_task(self.player_loop())

    def __str__(self):
        return f"channel ID {self.channel.id} (guild ID {self.guild.id})"

    @property
    def bot(self):
        return self.voice.client

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
        if self.voice.source:
            self.voice.source.volume = value

        self._volume = value

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        source = MusicAudioSource(self.now.filename, speed=value, start=self.position)
        self.voice.source = discord.PCMVolumeTransformer(source, self._volume)

        self._speed = value

    @property
    def position(self):
        if self.voice.source:
            return (self.voice.source.original.position / 1000) * self._speed

    @position.setter
    def position(self, value):
        source = MusicAudioSource(self.now.filename, speed=self._speed, start=value)
        self.voice.source = discord.PCMVolumeTransformer(source, self._volume)

    @property
    def is_playing(self):
        if self.now:
            return True
        else:
            return False

    @property
    def bar(self):
        decimal = self.position/self.now.total_seconds
        return "".join(["🔘" if x == int(decimal*30) else "▬" for x in range(30)])

    @property
    def embed(self):
        playing = ":pause_button:" if self.voice.is_playing() else ":arrow_forward:"
        looping = ":repeat:" if self.looping else ""

        em = discord.Embed(title=f"{playing}{looping} {self.now.title}", color=0x66FFCC)

        if self._speed != 1:
            em.description = f"{':fast_forward:' if self._speed >= 1 else ':rewind:'} Playback set to {int(self._speed) if int(self._speed) == self._speed else self._speed}x speed"

        em.set_thumbnail(url=self.now.thumbnail)
        em.add_field(name="Duration", value=f"{Song.parse_timestamp_duration(self.position)}/{self.now.timestamp_duration} `{self.bar}`", inline=False)
        em.add_field(name="Url", value=f"[Click]({self.now.url})")
        em.add_field(name="Uploader", value=f"[{self.now.uploader}]({self.now.uploader_url})")
        em.add_field(name="Requester", value=f"{self.now.requester.mention}")
        return em

    async def player_loop(self):
        log.info("PLAYER: Starting player loop for %s.", self)
        try:
            while True:
                # Get the next song from the queue, or wait for one to be added if the queue is empty
                if not self.now:
                    log.info("PLAYER: Getting a song from the queue for %s.", self)
                    queue_is_empty = self.queue.empty()

                    try:
                        self.now = await asyncio.wait_for(self.queue.get(), timeout=180)
                    except asyncio.TimeoutError:
                        log.info("PLAYER: Timed out while getting song from queue for %s. Cleaning up player.", self)
                        self.stop()
                        await self.voice.disconnect()

                        if self.guild.id in self.bot.players:
                            self.bot.players.pop(self.guild.id)

                        return

                if not self.voice.is_connected():
                    # The player is disconnected, wait until it reconnects to a voice channel
                    log.info("PLAYER: Waiting until bot is connected to play music in %s.", self)
                    await self.bot.loop.run_in_executor(None, self.voice._connected.wait)

                log.info("PLAYER: Playing a song in %s.", self)
                source = MusicAudioSource(self.now.filename, speed=self._speed)
                transformed = discord.PCMVolumeTransformer(source, self._volume)

                self.voice.play(transformed, after=self.after_song)

                query = """UPDATE songs
                           SET plays = plays + 1
                           WHERE songs.id=$1;
                        """
                await self.bot.db.execute(query, self.now.id)

                if self.notifications or queue_is_empty:
                    if self.now.interaction and not self.now.interaction.is_expired():
                        await self.now.interaction.followup.send(f":notes: Now playing `{self.now.title}`")
                        self.now.interaction = None
                    else:
                        await self.text_channel.send(f":notes: Now playing `{self.now.title}`")

                # Wait till the song is over and then resume the loop
                log.info("PLAYER: Waiting for song to finish in %s.", self)
                await self._event.wait()

                log.info("PLAYER: Song has finished in %s.", self)
                self._event.clear()

                if self.looping_queue:
                    await self.queue.put(self.now)
                if not self.looping or self._is_skip:
                    self.now = None
                    self._is_skip = False

        except Exception as exc:
            log.error("PLAYER: Exception in player loop for %s. Shutting down player.", self, exc_info=exc)

            if self.now or self.queue:
                await self.text_channel.send(f"Something went wrong and your music player crashed. Sorry about that!")

            await self.cleanup(stop_task=False)

    def after_song(self, exc):
        if exc:
            log.error("Exception in after function for %s", self, exc_info=exc)

        self._event.set()

    def pause(self):
        self.voice.pause()

    def resume(self):
        self.voice.resume()

    def skip(self):
        self._is_skip = True
        self.voice.stop()

    def stop(self):
        log.info("Stopping music for %s", self)
        self.now = None
        self.looping = False
        self.looping_queue = False

        self.queue.clear()
        self.voice.stop()

    async def cleanup(self, stop_task=True):
        if stop_task:
            log.info("Canceling player loop for %s", self)
            self.loop.cancel()

        self.stop()

        log.info("Deleting player for %s", self)
        if self.guild.id in self.bot.players:
            self.bot.players.pop(self.guild.id)

        log.info("Disconnecting from %s", self)
        await self.voice.disconnect()

class Song:
    __slots__ = ("_data", "interaction", "filename", "requester", "song_id", "extractor",
                 "uploader", "uploader_url", "date", "total_seconds", "upload_date",
                 "title", "thumbnail", "description", "duration", "timestamp_duration",
                 "tags", "url", "views", "likes", "dislikes",
                 "stream_url", "id", "plays", "created_at",
                 "updated_at")

    ytdl = yt_dlp.YoutubeDL({
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
    })

    def __init__(self, ctx, *, data, filename=None):
        self._data = data
        self.interaction = None
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
    async def from_query(cls, ctx, search,  *, search_only=False):
        # Check if the search and result is already cached in the database
        possible_song = await cls.from_alias(ctx, search)
        if possible_song:
            return await cls.confirm_download(ctx, possible_song)

        # This checks to see if the query is a youtube song name or id that is already cached in the database and returns the result if any is found
        if not search_only:
            youtube_id = cls.parse_youtube_id(search) or search
            query = """SELECT *
                    FROM songs
                    WHERE songs.song_id=$1 AND songs.extractor='youtube';
                    """
            record = await ctx.bot.db.fetchrow(query, youtube_id)
            if record:
                await cls.create_alias(ctx, search, record["id"])
                song = cls.from_record(record, ctx)
                return await cls.confirm_download(ctx, song)

        # Resolve the query into a full Song, so we can search the database
        song = await cls.resolve_query(ctx, search, ytsearch=search_only)
        query = """SELECT *
                   FROM songs
                   WHERE songs.song_id=$1 AND songs.extractor=$2;
                """
        record = await ctx.bot.db.fetchrow(query, song.song_id, song.extractor)
        if record:
            await cls.create_alias(ctx, search, record["id"])
            song = cls.from_record(record, ctx)
            return await cls.confirm_download(ctx, song)

        # We shouldn't get here unless the song isn't in the database
        song = await cls.download_song(ctx, song, extract_info=False)
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
    async def resolve_query(cls, ctx, search, *, ytsearch=False):
        partial = functools.partial(cls.ytdl.extract_info, f"{'ytsearch:' if ytsearch else ''}{search}", download=False)
        try:
            info = await ctx.bot.loop.run_in_executor(None, partial)
        except yt_dlp.DownloadError as exc:
            raise errors.SongError(str(exc)) from exc

        if not info:
            raise errors.SongError(f"I couldn't resolve `{search}`")
        if "entries" in info:
            entries = info["entries"]
            if not entries:
                raise errors.SongError(f"I couldn't find any results for `{search}`")
            info = entries[0]
        return cls(ctx, data=info, filename=cls.ytdl.prepare_filename(info))

    @classmethod
    async def download_song(cls, ctx, song, extract_info=True):
        if extract_info:
            try:
                partial = functools.partial(cls.ytdl.extract_info, song.url)
                info = await asyncio.wait_for(ctx.bot.loop.run_in_executor(None, partial), timeout=180)
            except yt_dlp.DownloadError as exc:
                raise errors.SongError(str(exc)) from exc
            except asyncio.TimeoutError as exc:
                raise errors.SongError(f"It took too long to download `{song.url}`") from exc

            if not info:
                raise errors.SongError(f"I Couldn't download `{song.url}`")
            if "entries" in info:
                entries = info["entries"]
                if not entries:
                    raise errors.SongError(f"I Couldn't find any results for `{search}`")
                info = entries[0]

            return cls(ctx, data=song._data, filename=cls.ytdl.prepare_filename(info))
        else:
            try:
                partial = functools.partial(cls.ytdl.process_info, song._data)
                await asyncio.wait_for(ctx.bot.loop.run_in_executor(None, partial), timeout=180)
            except yt_dlp.DownloadError as exc:
                    raise errors.SongError(str(exc)) from exc
            except asyncio.TimeoutError as exc:
                    raise errors.SongError(f"It took too long to download ’{song.url}’")

            return cls(ctx, data=song._data, filename=cls.ytdl.prepare_filename(song._data))

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
            info = await asyncio.wait_for(ctx.bot.loop.run_in_executor(None, partial), timeout=180)
        except yt_dlp.DownloadError as exc:
            raise errors.SongError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise errors.SongError("It took to long to download that playlist")
        if not info:
            raise errors.SongError(f"Couldn't find anything that matches `{search}`")
        if "entries" not in info:
            raise errors.SongError(f"No entries for `{search}`")

        if not len(info["entries"]):
            raise errors.SongError("This playlist is empty.")

        songs = []

        for data in info["entries"]:
            song = Song(ctx, data=data, filename=cls.ytdl.prepare_filename(data))
            songs.append(song)

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
        youtube_id = regex.fullmatch(url)
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
        if hours > 0 or days > 0:
            duration_str.append(f"{formats.plural(hours):hour}")
        if minutes > 0 or hours > 0 or days > 0:
            duration_str.append(f"{formats.plural(minutes):minute}")
        if seconds > 0 or minutes > 0 or hours > 0 or days > 0:
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

        if int(hours) > 0 and int(days) == 0:
            duration.append(int(hours))
        elif int(days) > 0:
            duration.append(f"{int(hours):02d}")

        if int(days) > 0 or int(hours) > 0:
            duration.append(f"{int(minutes):02d}")
        elif int(days) == 0 and int(hours) == 0:
            duration.append(int(minutes))

        duration.append(f"{int(seconds):02d}")

        return ":".join([str(x) for x in duration])

    @classmethod
    async def confirm_download(cls, ctx, song, extract_info=True):
        if os.path.exists(song.filename):
            new_song = song
        else:
            new_song = await cls.download_song(ctx, song, extract_info=extract_info)

            if new_song.filename != song.filename:
                query = """
                        UPDATE songs
                        SET filename=$1
                        WHERE songs.id=$2;
                        """
                await ctx.bot.db.execute(query, new_song.filename, song.id)

        return new_song

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

        self.spotify = spotify.Spotify(
            self.bot.session,
            client_id=getattr(self.bot.config, "spotify_client_id", None),
            client_secret=getattr(self.bot.config, "spotify_client_secret", None)
        )

        self.loop._fallback_command.wrapped.cog = self
        self.queue._fallback_command.wrapped.cog = self

    def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage()

        return True

    @commands.hybrid_command(name="join", description="Connect the bot to a voice channel", aliases=["connect"])
    @commands.guild_only()
    async def join(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send("You are not connected to a voice channel.")

        if ctx.guild.id in self.bot.players and ctx.voice_client:
            return await ctx.send("I'm already connected to a voice channel.")

        if ctx.guild.id in self.bot.players or ctx.voice_client: 
            # Weird broken voice state stuff
            log.warning("Cannot connect to channel ID %s (guild ID %s) because the voice state is broken. Attempting to fix before connecting.", channel.id, ctx.guild.id)

            if ctx.guild.id in self.bot.players:
                self.bot.players.pop(ctx.guild.id)

            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)

            if ctx.guild.id in self.bot._connection._voice_clients:
                self.bot._connection._voice_clients.pop(ctx.guild.id)

        if not channel.permissions_for(ctx.me).connect:
            return await ctx.send(f"I don't have permission to connect to {channel.mention}.")
        elif channel.user_limit and len(channel.members) >= channel.user_limit and not ctx.me.guild_permissions.move_members:
            return await ctx.send(f"I can't connect to {channel.mention} because it's full.")

        log.info("Attempting to connect to channel ID %s (guild ID %s).", channel.id, ctx.guild.id)
        try:
            voice_client = await channel.connect(cls=MusicVoiceClient)
        except Exception as exc:
            log.warning("Failed to connect to channel ID %s (guild ID %s).", channel.id, ctx.guild.id, exc_info=exc)
            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)
            if ctx.guild.id in self.bot._connection._voice_clients:
                log.warning("Removing broken voice connection to channel ID %s (guild ID %s).", channel.id, ctx.guild.id)
                self.bot._connection._voice_clients.pop(ctx.guild.id)

            return await ctx.send(f"Something went wrong while connecting to {channel.mention}")

        player = self.bot.players[ctx.guild.id] = MusicPlayer(voice_client, ctx.channel)

        if isinstance(channel, discord.StageChannel):
            # Make sure we can talk in a stae channel
            log.info("Attempting to become a speaker in %s", player)

            try:
                await ctx.me.edit(suppress=False)
                log.info("Successfully became a speaker in %s", player)
            except discord.Forbidden:
                log.warning("Requesting to speak in %s because we weren't able to un-suppress", player)
                await ctx.me.request_to_speak()

        if ctx.command not in [self.play, self.search] or not ctx.interaction:
            await ctx.send(f"Connected to {channel.mention}")

        log.info("Successfully connected to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)

    @commands.hybrid_command(name="summon", description="Summon the bot to a different channel")
    @commands.guild_only()
    async def summon(self, ctx):
        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            return await ctx.send("You are not connected to a voice channel.")

        if not channel.permissions_for(ctx.me).connect:
            await ctx.send(f"I don't have permission to connect to {channel.mention}.")
        elif channel.user_limit and len(channel.members) >= channel.user_limit and not ctx.me.guild_permissions.move_members:
            await ctx.send(f"I can't connect to {channel.mention} because it's full.")

        log.info("Moving player in %s to channel ID %s", ctx.player, channel.id)
        await ctx.guild.change_voice_state(channel=channel)

        log.info("Successfully moved player to %s", ctx.player)
        ctx.player.text_channel = ctx.channel

        await ctx.send(f"Now connected to {channel.mention} and bound to {ctx.channel.mention}")

    @commands.hybrid_command(name="play", description="Play a song", aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, query: PossibleURL):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")

        if not ctx.interaction:
            await ctx.send(f":mag: Searching for `{query}`")

        spotify_match = re.fullmatch(r"(?:http[s]?://open.spotify.com/)([A-Za-z]+)(?:/)([a-zA-Z0-9]+)(?:.+)", query)

        if spotify_match:
            resource_type = spotify_match.group(1)
            resource_id = spotify_match.group(2)

            async with ctx.typing():
                try:
                    if resource_type == "track":
                        tracks = [await self.spotify.get_track(resource_id)]
                    elif resource_type == "album":
                        tracks = await self.spotify.get_album(resource_id)
                    elif resource_type == "playlist":
                        tracks = await self.spotify.get_playlist(resource_id)
                    else:
                        return await ctx.send(f"The only supported Spotify links are tracks, albums, and playlists.")
                except spotify.ResourceNotFound as exc:
                    return await ctx.send(str(exc))

                if resource_type in ("playlist", "album"):
                    for track in tracks:
                        song = await Song.from_query(ctx, track, search_only=True)
                        await ctx.player.queue.put(song)

                    await ctx.send(f":notepad_spiral: Finished downloading {formats.plural(len(tracks)):song} from Spotify")
                else:
                    song = await Song.from_query(ctx, tracks[0], search_only=True)
                    await ctx.player.queue.put(song)

                    if ctx.player.is_playing:
                        await ctx.send(f":page_facing_up: Enqueued `{song.title}`")
                    elif ctx.interaction:
                        song.interaction = ctx.interaction

        elif "list=" in query:
            if not ctx.interaction:
                await ctx.send(":globe_with_meridians: Downloading playlist")

            async with ctx.typing():
                songs = await Song.playlist(ctx, query)
                for song in songs:
                    await ctx.player.queue.put(song)

            await ctx.send(f":notepad_spiral: Finished downloading {formats.plural(len(songs)):song} from playlist")
        else:
            async with ctx.typing():
                song = await Song.from_query(ctx, query)

            await ctx.player.queue.put(song)

            if ctx.player.is_playing:
                await ctx.send(f":page_facing_up: Enqueued `{song.title}`")
            elif ctx.interaction:
                song.interaction = ctx.interaction

    @commands.hybrid_command(name="search", description="Search for a song on youtube")
    @commands.guild_only()
    async def search(self, ctx, *, query):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")

        async with ctx.typing():
            songs = await Song.playlist(ctx, f"ytsearch5:{query}", download=False)

        if not songs:
            return await ctx.send("I couldn't find any results for `{query}`")

        view = SongSelectorView(ctx, songs)
        view.message = await ctx.send(embed=view.embed, view=view)

    @commands.hybrid_command(name="pause", description="Pause the music")
    @commands.guild_only()
    async def pause(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now or ctx.player.voice.is_paused():
            return await ctx.send("Already paused")

        ctx.player.pause()
        await ctx.send(":arrow_forward: Paused")

    @commands.hybrid_command(name="resume", description="Resume the music")
    @commands.guild_only()
    async def resume(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now or ctx.player.voice.is_playing():
            return await ctx.send("Already playing")

        ctx.player.resume()
        await ctx.send(":pause_button: Resumed")

    @commands.hybrid_command(name="startover", description="Start the current song from the beginning")
    @commands.guild_only()
    async def startover(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        ctx.player.position = 0

        await ctx.send(":rewind: Starting over")

    @commands.hybrid_command(name="seek", description="Seek a position in the song", aliases=["seekto", "position"])
    @commands.guild_only()
    async def seek(self, ctx, *, position: PositionConverter):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        if position > ctx.player.now.total_seconds or position < 0:
            return await ctx.send("That is not a valid position")

        emoji = ":fast_forward:" if position >= ctx.player.position else ":rewind:"
        ctx.player.position = position

        await ctx.send(f"{emoji} Seeked `{Song.parse_timestamp_duration(position)}`")

    @commands.hybrid_command(name="speed", description="Change the playback speed of the song", aliases=["speedup", "slowdown"])
    @commands.guild_only()
    async def speed(self, ctx, *, speed: typing.Optional[float]):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        if not speed:
            emoji = ":fast_forward:" if ctx.player.speed >= 1 else ":rewind:"
            return await ctx.send(f"{emoji} Playback speed is set to {int(ctx.player.speed) if int(ctx.player.speed) == ctx.player.speed else ctx.player.speed}x speed")

        if speed < 0.5 or speed > 2:
            return await ctx.send("Playback speed must from 0.5x to 2x.")

        ctx.player.speed = speed

        emoji = ":fast_forward:" if speed >= 1 else ":rewind:"
        await ctx.send(f"{emoji} Playback is now set to {int(speed) if int(speed) == speed else speed}x speed")

    @commands.hybrid_command(name="skip", description="Skip the music", aliases=["s"])
    @commands.guild_only()
    async def skip(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        ctx.player.skip()
        await ctx.send(":track_next: Skipped current song")

    @commands.hybrid_command(name="skipto", description="Jump to a song in the queue")
    @commands.guild_only()
    async def skipto(self, ctx, position: int):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        if position == 0 or position > len(ctx.player.queue):
            return await ctx.send("That is not a song in the queue")

        position = position - 1

        # Remove all the song (and add them back to the end if looping) until we reach the song we want to skip to
        for x in range(position):
            current = await ctx.player.queue.get()
            if ctx.player.looping_queue:
                await ctx.player.queue.put(current)

        ctx.player.skip()
        song = ctx.player.queue[0]
        await ctx.send(f":track_next: Jumped to `{song.title}`")

    @commands.hybrid_group(name="loop", fallback="song", description="Toggle the song loop", aliases=["repeat"], invoke_without_command=True)
    @commands.guild_only()
    async def loop(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        ctx.player.looping_queue = False

        if ctx.player.looping:
            ctx.player.looping = False
            await ctx.send(":x::repeat_one: Unlooped song")
        else:
            ctx.player.looping = True
            await ctx.send(":repeat_one: Looped song")

    @loop.command(name="queue", description="Toggle the queue loop")
    async def loop_queue(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.queue:
            return await ctx.send("Nothing is queued")

        ctx.player.looping = False

        if ctx.player.looping_queue:
            ctx.player.looping_queue = False
            await ctx.send(":x::repeat: Unlooped queue")
        else:
            ctx.player.looping_queue = True
            await ctx.send(":repeat: Looping queue")

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue")
    @commands.guild_only()
    async def shuffle(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.queue:
            return await ctx.send("Nothing is queued to play")

        ctx.player.queue.shuffle()
        await ctx.send(":twisted_rightwards_arrows: Shuffled the queue")

    @commands.hybrid_command(name="volume", description="Set the volume")
    @commands.guild_only()
    async def volume(self, ctx, volume: typing.Optional[int]):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.now:
            return await ctx.send("Nothing is playing")

        if volume is None:
            emoji = ":loud_sound:" if ctx.player.volume >= 50 else ":sound:"
            return await ctx.send(f"{emoji} `{int(ctx.player.volume * 100)}%`")
        if volume < 0 or volume > 100:
            return await ctx.send(":Volume must be between 0 and 100")

        ctx.player.volume = volume / 100
        emoji = ":loud_sound:" if volume >= 50 else ":sound:"
        await ctx.send(f"{emoji} Volume set to `{volume}%`")

    @commands.hybrid_command(name="notify", description="Toggle now playing messages")
    @commands.guild_only()
    async def notify(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")

        if ctx.player.notifications:
            ctx.player.notifications = False
            await ctx.send(":no_bell: Notifications disabled")
        else:
            ctx.player.notifications = True
            await ctx.send(":bell: Notifications enabled")

    @commands.hybrid_command(name="stop", description="Stop the music")
    @commands.guild_only()
    async def stop(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")

        ctx.player.stop()
        await ctx.send(":stop_button: Stopped music and cleared queue")

    @commands.hybrid_command(name="now", description="Get the current playing song", aliases=["np"])
    @commands.guild_only()
    async def now(self, ctx):
        if not ctx.player.now:
            return await ctx.send("Not playing anything")

        await ctx.send(embed=ctx.player.embed)

    @commands.hybrid_command(name="next", description="View the next song in the queue", aliases=["nextup"])
    @commands.guild_only()
    async def next_(self, ctx):
        if not ctx.player.queue:
            return await ctx.send("Nothing is queued to play")

        song = ctx.player.queue[0]
        await ctx.send(embed=song.embed)

    @commands.hybrid_group(name="queue", fallback="show", description="View the queue", invoke_without_command=True)
    @commands.guild_only()
    async def queue(self, ctx, position: typing.Optional[int]):
        if not ctx.player.queue:
            return await ctx.send("Nothing is queued to play")

        if not position:
            view = QueueView(ctx.player)
            view.message = await ctx.send(embed=view.embed, view=view)
        else:
            if position == 0 or position > len(ctx.player.queue):
                return await ctx.send("That is not a song in the queue")

            song = ctx.player.queue[position-1]
            await ctx.send(embed=song.embed)

    @queue.command(name="remove", description="Remove a song from the queue")
    async def queue_remove(self, ctx, position: int):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif position < 0 or position > len(ctx.player.queue):
            return await ctx.send("That is not a valid queue position")

        song = ctx.player.queue[position-1]
        ctx.player.queue.remove(song)
        await ctx.send(f":wastebasket: Removed `{song.title}` from queue")

    @queue.command(name="clear", description="Clear the queue")
    async def queue_clear(self, ctx):
        if ctx.author not in ctx.player.channel.members:
            return await ctx.send("You are not listening to the music")
        elif not ctx.player.queue:
            return await ctx.send("Nothing is queued to play")

        ctx.player.queue.clear()
        await ctx.send(":wastebasket: Cleared queue")

    @commands.hybrid_command(name="leave", description="Disconnect the bot from a voice channel", aliases=["disconnect"])
    async def leave(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        # We appearently aren't in a voice channel
        if not player and not ctx.voice_client:
            await ctx.send("I'm not connected to any voice channel.")

        # Normal disconnect
        if player:
            channel = player.channel

            if ctx.author not in player.channel.members:
                return await ctx.send("You are not listening to the music")

            log.info("Disconnecting from %s normally.", player)

            await player.cleanup()
            await ctx.send(f"Disconnected from {channel.mention}")

            log.info("Disconnected from %s normally.", player)

        # Weird situation where discord.py thinks we're connected but there's no player
        if ctx.voice_client:
            channel = ctx.voice_client.channel
            log.warning("Disconnecting from channel ID %s (guild ID %s) forcefully.", channel.id, ctx.guild.id)

            await ctx.voice_client.disconnect(force=True)

            if not player:
                await ctx.send(f"Disconnected from {channel.mention}")

            log.warning("Disconnected from channel ID %s (guild ID %s) forcefully.", channel.id, ctx.guild.id)

        # Fix voice clients state cause something completely broke
        if ctx.guild.id in self.bot._connection._voice_clients:
            log.warning("Removing broken voice connection to channel ID %s (guild ID %s).", channel.id, ctx.guild.id)
            self.bot._connection._voice_clients.pop(ctx.guild.id)

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
            return await ctx.send(f"I don't have any songs in my database")

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
            return await ctx.send(f"I couldn't find any songs in the database that matched `{search}`")

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
            info = f"{player.guild} - `{player.channel} | {player.text_channel}`"
            latency = f"{player.latency*1000:.2f}ms"
            players.append(f"{info} ({latency})")

        await ctx.send("\n".join(players))

    @commands.command(name="stopall", description="Stop all players")
    @commands.is_owner()
    async def stopall(self, ctx):
        player_count = await self.bot.stop_players()
        await ctx.send(f"{formats.plural(player_count):player} stopped.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        player = self.bot.players.get(member.guild.id)

        if not player:
            return

        stage_success = True

        if after.channel and member == self.bot.user and isinstance(after.channel, discord.StageChannel) and before.channel != after.channel:
            # Attempt to un-suppress
            log.info("Attempting to become a speaker in %s.", player)

            try:
                await member.edit(suppress=False)
                log.info("Successfully became a speaker in %s.", player)
            except discord.Forbidden:
                # Set a note to request to become a speaker at the end
                stage_success = False
                log.warning("In-sufficient permission to become a speaker %s.", player)

        # Check if the bot is in an empty channel, and wait for members if it is
        if not [member for member in player.channel.members if not member.bot]:
            # Pause the player while the bot waits for someone to join
            was_paused = player.voice.is_paused()

            player.pause()
            log.info("Voice channel %s is empty. Waiting for someone to join.", player)

            try:
                check = lambda member, before, after: (not member.bot and after.channel and after.channel == player.channel) or (member.id == self.bot.user.id and after.channel and after.channel != before.channel)
                await self.bot.wait_for("voice_state_update", timeout=180, check=check)
                log.info("Someone joined %s. Continuing player.", player)

                # Resume the player if it was not already paused
                if not was_paused:
                    player.resume()

            except asyncio.TimeoutError:
                # Disconnect because there was no activity for 3 minutes
                log.info("Timed out while waiting for someone to join %s.", player)
                now_playing = player.now

                await player.cleanup()

                if now_playing:
                    await player.text_channel.send(f"I left {player.voice.channel.mention} because it no one was listening.")

                return

        if not stage_success:
            log.warning("Requesting to speak in %s.", player)
            await member.request_to_speak()

    @play.before_invoke
    @search.before_invoke
    async def create_player(self, ctx):
        if ctx.guild.id not in self.bot.players:
            log.info("Connecting to voice in guild ID %s before invoking command.", ctx.guild.id)
            await self.join(ctx)

            if ctx.guild.id not in self.bot.players:
                raise errors.VoiceError()

        ctx.player = self.bot.players[ctx.guild.id]

    @summon.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    @startover.before_invoke
    @seek.before_invoke
    @speed.before_invoke
    @skip.before_invoke
    @skipto.before_invoke
    @loop.before_invoke
    @loop_queue.before_invoke
    @shuffle.before_invoke
    @volume.before_invoke
    @notify.before_invoke
    @stop.before_invoke
    @now.before_invoke
    @next_.before_invoke
    @queue.before_invoke
    @queue_remove.before_invoke
    @queue_clear.before_invoke
    async def get_player(self, ctx):
        player = self.bot.players.get(ctx.guild.id)

        if not player:
            if ctx.voice_client:
                # The bot *might* be connected or it might not, so just make sure we disconnect just in case
                log.warning("BEFORE INVOKE: A voice client exists for guild ID %s even though a player doesn't.", ctx.guild.id)
                await ctx.voice_client.disconnect(force=True)

            if ctx.guild.id in self.bot._connection._voice_clients:
                # Something weird is happening
                log.warning("BEFORE INVOKE: Removing broken voice connection to channel ID %s (guild ID %s)", channel.id, ctx.guild.id)
                self.bot._connection._voice_clients.pop(ctx.guild.id)

            raise errors.VoiceError("I'm not connected to any voice channel.")

        ctx.player = player

async def setup(bot):
    await bot.add_cog(Music(bot))
