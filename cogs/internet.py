from discord.ext import commands
from discord.ext import menus
import discord

import io
import os

import re
import zlib
from bs4 import BeautifulSoup
import aiohttp

import dateparser

from .utils import custom

class DocsPages(menus.ListPageSource):
    """Pages for showing documentation results"""

    def __init__(self, data, search, ctx):
        self.search = search
        self.data = data
        self.ctx = ctx
        self.bot = ctx.bot
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        em = self.bot.build_embed(title=f"Results for search '{self.search}'", description="", color=custom.Color.discord)
        for i, v in enumerate(entries, start=offset):
            em.description += "\n[`"+v[0]+"`]("+v[1]+")"
        em.set_footer(text=f"{len(self.data)} results | Page {menu.current_page+1}/{int(len(self.data)/10)+1}")

        return em
class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')

def finder(text, collection, *, key=None, lazy=True):
    suggestions = []
    text = str(text)
    pat = '.*?'.join(map(re.escape, text))
    regex = re.compile(pat, flags=re.IGNORECASE)
    for item in collection:
        to_search = key(item) if key else item
        r = regex.search(to_search)
        if r:
            suggestions.append((len(r.group()), r.start(), item))

    def sort_key(tup):
        if key:
            return tup[0], tup[1], key(tup[2])
        return tup

    if lazy:
        return (z for _, _, z in sorted(suggestions, key=sort_key))
    else:
        return [z for _, _, z in sorted(suggestions, key=sort_key)]

class Internet(commands.Cog):
    """Internet commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":globe_with_meridians:"

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_docs_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            sub = cache[key] = {}
            async with self.bot.session.get(page + "/objects.inv") as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        "Cannot build docs lookup table, try again later."
                    )

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._docs_cache = cache

    async def do_docs(self, ctx, key, obj):
        page_types = {
            "latest": "https://discordpy.readthedocs.io/en/latest",
            "python": "https://docs.python.org/3"
        }

        if obj is None:
            await ctx.send(page_types[key])
            return

        if not hasattr(self, "_docs_cache"):
            await ctx.trigger_typing()
            await self.build_docs_lookup_table(page_types)

        obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

        if key.startswith("latest") or key.startswith("stable"):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == "_":
                    continue
                if q == name:
                    obj = f"abc.Messageable.{name}"
                    break

        cache = list(self._docs_cache[key].items())

        def transform(tup):
            return tup[0]

        matches = finder(obj, cache, key=lambda t: t[0], lazy=False)

        if len(matches) == 0:
            return await ctx.send("Could not find anything. Sorry.")
        
        pages = menus.MenuPages(source=DocsPages(matches, obj, ctx), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(name="docs", description="Get a link for docs on discord.py", invoke_without_command=True)
    async def docs(self, ctx, obj=None):
        await self.do_docs(ctx, "latest", obj)

    @docs.command(name="py", description="Get a link for docs on python")
    async def py_docs(self, ctx, obj=None):
        await self.do_docs(ctx, "python", obj)

    @commands.cooldown(1, 20, commands.BucketType.user)
    @commands.group(name="github", description="Get infromation about a GitHub repository", invoke_without_command=True)
    async def github(self, ctx, repo):
        #Trigger typing, this takes a little
        await ctx.channel.trigger_typing()
        session = self.bot.session

        async with session.get(f"https://api.github.com/repos/{repo}") as response:
            data = await response.json()
        if data.get("message") == "Not Found":
            return await ctx.send("Repository not found")

        async with session.get(f"https://api.github.com/repos/{repo}/releases") as response:
            releases_data = await response.json()
          
        em = self.bot.build_embed(title=data.get("name"), description=data.get("description"), url=data.get("html_url"), color=custom.Color.github)
        em.add_field(name="Language", value=data.get("language"))
        em.add_field(name="Branch", value=data.get("default_branch"))
        em.add_field(name="Stars", value=data.get("stargazers_count"))
        em.add_field(name="Watching", value=data.get("watchers_count"))
        em.add_field(name="Forks", value=data.get("forks"))

        releases = ""
        for release in releases_data:
            releases += f"\n[{release.get('tag_name')}]({release.get('html_url')})"
        
        if releases != "":
            em.add_field(name="Releases", value=releases)

        em.set_thumbnail(url=data.get("owner").get("avatar_url"))
        await ctx.send(embed=em)


    @commands.cooldown(1, 20, commands.BucketType.user)
    @github.command(name="user", description="Get a GitHub user")
    async def github_user(self, ctx, user):
        #Trigger typing, this takes a little
        await ctx.channel.trigger_typing()
        session = self.bot.session
        async with session.get(f"https://api.github.com/users/{user}") as response:
            data = await response.json()

        if data.get("message") == "Not Found":
            return await ctx.send("User not found")


        em = self.bot.build_embed(title=data.get("login"), description=data.get("bio"), url=data.get("html_url"), color=custom.Color.github)
        em.add_field(name="Repositories", value=data.get("public_repos"))
        em.add_field(name="Gists", value=data.get("public_gists"))
        em.add_field(name="Followers", value=data.get("followers"))
        em.add_field(name="Following", value=data.get("following"))
        
        if data.get("blog") != "":
            em.add_field(name="Blog", value=data.get("blog"))
        em.set_thumbnail(url=data.get("avatar_url"))
        await ctx.send(embed=em)

    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command(name="roblox", description="Get a Roblox user")
    async def roblox(self, ctx, username):
        #Roblox is a bit strange, you have to use a differnet url for each bit of info
        await ctx.channel.trigger_typing()
        session = self.bot.session
        async with session.get(f"http://api.roblox.com/users/get-by-username/?username={username}") as resp:
            data = await resp.json()
            if "Id" not in data:
                return await ctx.send("Sorry, that user is not found")
        
        userid = data["Id"]
        async with session.get(f"https://users.roblox.com/v1/users/{userid}") as resp:
            data = await resp.json()
        
        #Parse html to get profile image, roblox doesn't have this in the API
        async with session.get(f"https://www.roblox.com/users/{userid}/profile") as resp:
            html = await resp.read()
            html = html.decode("utf-8")

            soup = BeautifulSoup(html , 'html.parser')
            links = soup.find_all("img")
            avatar_url = links[0].get("src")         

        em = self.bot.build_embed(title=data["displayName"], description=data["description"], url=f"https://roblox.com/users/{userid}", timestamp=dateparser.parse(data["created"]))

        async with session.get(f"https://users.roblox.com/v1/users/{userid}/status") as resp:
            status = await resp.json()
        
        if status["status"] != "":
            em.add_field(name="Status", value=status["status"])

        async with session.get(f"https://friends.roblox.com/v1/users/{userid}/friends/count") as resp:
            friends = await resp.json()
        
        em.add_field(name="Friends Count", value=friends["count"])

        em.set_thumbnail(url=avatar_url)

        em.set_footer(text="Created at")

        await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Internet(bot))