import discord
from discord.ext import commands, menus

import io
import os
import re
import zlib
import aiohttp
import datetime
import dateparser
import json
import base64
import functools
from PIL import Image
from bs4 import BeautifulSoup

class DocsPages(menus.ListPageSource):
    def __init__(self, data, search):
        self.search = search
        self.data = data
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        em = discord.Embed(title=f"Results for '{self.search}'", description="", color=0x96c8da)
        for i, v in enumerate(entries, start=offset):
            em.description += "\n[`"+v[0]+"`]("+v[1]+")"
        em.set_footer(text=f"{len(self.data)} results | Page {menu.current_page+1}/{int(len(self.data)/10)+1}")

        return em

class GoogleResultPages(menus.ListPageSource):
    def __init__(self, data, search):
        self.search = search
        self.data = data
        super().__init__(data, per_page=1)

    async def format_page(self, menu, entry):
        em = discord.Embed(title=entry["title"], url=entry["link"], color=0x96c8da)
        if entry.get("snippet"):
           em.description = entry["snippet"]

        try:
            image = entry["pagemap"]["cse_thumbnail"][0]["src"]
            em.set_thumbnail(url=image)
        except KeyError:
            pass

        em.set_author(name=f"Results for '{self.search}'")
        em.set_footer(text=f"{len(self.data)} results | Page {menu.current_page+1}/{len(self.data)}")

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
            "asyncpg": "https://magicstack.github.io/asyncpg/current/",
            "pillow": "https://pillow.readthedocs.io/en/latest",
            "tpy": "https://telegrampy.readthedocs.io/en/latest",
            "python": "https://docs.python.org/3"
        }

        if obj is None:
            await ctx.send(page_types[key])
            return

        if not hasattr(self, "_docs_cache"):
            await ctx.trigger_typing()
            await self.build_docs_lookup_table(page_types)

        obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)
        obj = re.sub(r"^(?:telegrampy\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

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
            return await ctx.send("Could not find anything")
        
        pages = menus.MenuPages(source=DocsPages(matches, obj), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(name="docs", description="Search Discord.py docs", invoke_without_command=True)
    async def docs(self, ctx, obj=None):
        await self.do_docs(ctx, "latest", obj)

    @docs.command(name="python", description="Search Python docs", aliases=["py"])
    async def docs_python(self, ctx, obj=None):
        await self.do_docs(ctx, "python", obj)

    @docs.command(name="asyncpg", description="Search Asyncpg docs")
    async def docs_asyncpg(self, ctx, obj=None):
        await self.do_docs(ctx, "asyncpg", obj)

    @docs.command(name="pillow", descrption="Search Pillow docs", aliases=["pil"])
    async def docs_pillow(self, ctx, obj=None):
        await self.do_docs(ctx, "pillow", obj)

    @docs.command(name="telegram", description="Search Telegram.py docs", aliases=["telegrampy", "telegram.py", "tpy"])
    async def docs_telegram(self, ctx, obj=None):
        await self.do_docs(ctx, "tpy", obj)

    @commands.command(name="roblox", description="Get a Roblox user")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def roblox(self, ctx, username):
        await ctx.channel.trigger_typing()
        session = self.bot.session
        async with session.get(f"http://api.roblox.com/users/get-by-username/?username={username}") as resp:
            data = await resp.json()
            if "Id" not in data:
                return await ctx.send("Sorry, that user is not found")
        userid = data["Id"]

        #Make API requests
        async with session.get(f"https://users.roblox.com/v1/users/{userid}") as resp:
            data = await resp.json()
        async with session.get(f"https://users.roblox.com/v1/users/{userid}/status") as resp:
            status = await resp.json()
        async with session.get(f"https://friends.roblox.com/v1/users/{userid}/friends/count") as resp:
            friends = await resp.json()

        #Parse html to get profile image
        async with session.get(f"https://www.roblox.com/users/{userid}/profile") as resp:
            html = await resp.read()
            html = html.decode("utf-8")
            soup = BeautifulSoup(html , 'html.parser')
            links = soup.find_all("img")
            avatar_url = links[0].get("src")         

        em = discord.Embed(title=data["displayName"], description=data["description"], url=f"https://roblox.com/users/{userid}", timestamp=dateparser.parse(data["created"]), color=0x96c8da)
        if status["status"]:
            em.add_field(name="Status", value=status["status"]) 
        em.add_field(name="Friends Count", value=friends["count"])
        em.set_thumbnail(url=avatar_url)
        em.set_footer(text="Created at")
        await ctx.send(embed=em)

    @commands.command(name="minecraft", description="Get info on a minecraft user", aliases=["mc"])
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def minecraft(self, ctx, *, username):
        async with self.bot.session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as resp:
            if resp.status != 200:
                return await ctx.send(":x: Could not fetch Minecraft user")

            data = await resp.json()
        name = data["name"]
        uuid = data["id"]

        async with self.bot.session.get(f"https://api.mojang.com/user/profiles/{uuid}/names") as resp:
            name_history = await resp.json()
        names = []
        for name_data in reversed(name_history):
            timestamp = name_data.get("changedToAt")
            old_name = name_data["name"]
            if timestamp:
                seconds = timestamp / 1000
                time = datetime.datetime.fromtimestamp(seconds + (timestamp % 1000.0) / 1000.0)
                time = time.strftime("%m/%d/%y")
                names.append(f"{old_name} ({time})")
            else:
                names.append(old_name)

        async with self.bot.session.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}") as resp:
            data = await resp.json()
        data = data["properties"][0]["value"]
        data = json.loads(base64.b64decode(data))
        url = data["textures"]["SKIN"]["url"]

        async with self.bot.session.get(url) as resp:
            data = await resp.read()
            image = io.BytesIO(data)

        partial = functools.partial(Image.open, image)
        image = await self.bot.loop.run_in_executor(None, partial)

        partial = functools.partial(image.crop, (8, 8, 16, 16))
        image = await self.bot.loop.run_in_executor(None, partial)

        partial = functools.partial(image.resize, (500, 500), resample=Image.NEAREST)
        image = await self.bot.loop.run_in_executor(None, partial)

        output = io.BytesIO()
        image.save(output, format="png")
        output.seek(0)

        em = discord.Embed(title=name)
        em.set_thumbnail(url="attachment://face.png")
        em.add_field(name="Names", value="\n".join(names))
        em.set_footer(text=f"ID: {uuid}")

        await ctx.send(embed=em, file=discord.File(output, filename="face.png"))

    @commands.command(name="wikipedia", descroption="Search wikipedia", aliases=["wiki"])
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def wikipedia(self, ctx, *, search):
        url = "http://en.wikipedia.org/w/api.php"

        data = {"prop": "info|pageprops", "inprop": "url", "ppprop": "disambiguation", "redirects": "", "titles": search, "format": "json", "action": "query"}
        async with self.bot.session.get(url, params=data) as resp:
            if resp.status != 200:
                return await ctx.send(f":x: Failed to fetch page data (error code {resp.status})")
            page_data = await resp.json()
            pages = page_data["query"]["pages"]
            page_id = list(page_data["query"]["pages"].keys())[0]
            page = pages[page_id]
            if "pageid" not in page:
                return await ctx.send(f":x: Could not find a page with the name '{search}'")

        data = {"prop": "extracts", "explaintext": "", "pageids": page_id, "format": "json", "action": "query"}
        async with self.bot.session.get(url, params=data) as resp:
            if resp.status != 200:
                return await ctx.send(f":x: Failed to fetch page data (error code {resp.status})")
            summary_data = await resp.json()
            summary = summary_data["query"]["pages"][page_id]["extract"]

        summary = summary.replace("===", "__")
        summary = summary.replace("==", "**")
        description = f"{summary[:1000]}{'...' if len(summary) > 1000 else ''}\n\n[Read more]({page['fullurl']})"

        em = discord.Embed(title=f"{page['title']} ({page_id})", description=description, url=page["fullurl"])
        await ctx.send(embed=em)

    @commands.command(name="google", description="Search google")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def google(self, ctx, *, search):
        results = await self.search_google(search)
        pages = menus.MenuPages(GoogleResultPages(results, search), clear_reactions_after=True)
        await pages.start(ctx)

    async def search_google(self, query):
        async with self.bot.session.get(f"{self.bot.config.google_url}&q={query}") as resp:
            data = await resp.json()
            return data["items"]

    @commands.command(name="github", description="Get info on a GitHub item", aliases=["gh"])
    @commands.cooldown(3, 30, commands.BucketType.user)
    async def github(self, ctx, *, item):
        if "/" in item:
            async with self.bot.session.get(f"https://api.github.com/repos/{item}") as resp:
                if resp.status != 200:
                    return await ctx.send(":x: Could not fetch GitHub repository")
                data = await resp.json()
                owner = data["owner"]

            em = discord.Embed(title=data["full_name"], description=f"{data['description'] or ''}\n{data['homepage'] or ''}", url=data["html_url"], timestamp=dateparser.parse(data["created_at"]), color=0x96c8da)
            em.set_author(name=owner["login"], url=owner["html_url"], icon_url=owner["avatar_url"])
            em.set_thumbnail(url=owner["avatar_url"])
            em.add_field(name="Language", value=data["language"])
            em.add_field(name="Stars", value=data["stargazers_count"])
            em.add_field(name="Watching", value=data["watchers_count"])
            em.add_field(name="Forks", value=data["forks_count"])
            em.set_footer(text="Created")
        else:
            async with self.bot.session.get(f"https://api.github.com/users/{item}") as resp:
                if resp.status != 200:
                    return await ctx.send(":x: Could not fetch GitHub user")
                data = await resp.json()

            em = discord.Embed(title=data["login"], description=data['bio'], url=data["html_url"], timestamp=dateparser.parse(data["created_at"]), color=0x96c8da)
            em.set_thumbnail(url=data["avatar_url"])
            em.add_field(name="Repositories", value=data["public_repos"])
            em.add_field(name="Gists", value=data["public_gists"])
            em.add_field(name="Followers", value=data["followers"])
            em.add_field(name="Following", value=data["following"])
            if data["blog"]:
                em.add_field(name="Website", value=data["blog"])
            em.set_footer(text="Created")

        await ctx.send(embed=em)

    @commands.command(name="pypi", description="Search for a project on PyPI", aliases=["pip", "project"])
    @commands.cooldown(3, 30, commands.BucketType.user)
    async def pypi(self, ctx, project, release=None):
        if release:
            url = f"https://pypi.org/pypi/{project}/{release}/json"
        else:
            url = f"https://pypi.org/pypi/{project}/json"

        async with self.bot.session.get(url) as resp:
            if resp.status != 200:
                return await ctx.send(f":x: Could not fetch package")
            data = await resp.json()
            info = data["info"]
            releases = data["releases"]

        em = discord.Embed(title=info["name"], description=info["summary"], url=info["package_url"], color=0x96c8da)
        em.set_thumbnail(url="https://i.imgur.com/6WHMGed.png")
        em.set_author(name=info["author"] + " " + (f"({info['author_email']})" if info['author_email'] else ""))

        if info["home_page"]:
            em.add_field(name="Home Page", value=info["home_page"])
        if info["license"]:
            em.add_field(name="License", value=info["license"])
        if info["requires_python"]:
            em.add_field(name="Required Python", value=info["requires_python"])
        if releases:
            em.add_field(name=f"Releases ({len(releases)} total)",
            value="\n".join([f"[{release}]({info['package_url']}{release})" for release in list(releases.keys())[:5]]) +
            (f"\n... and {len(releases)-5} more" if len(releases) > 5 else ""))
        if info["project_urls"]:
            em.add_field(name=f"Project Links ({len(info['project_urls'])} total)",
            value="\n".join([f"[{item[0]}]({item[1]})" for item in list(info["project_urls"].items())[:5]]) +
            (f"\n... and {len(info['project_urls'])-5} more" if len(info["project_urls"]) > 5 else ""))
        if info["classifiers"]:
            em.add_field(name=f"Classifiers ({len(info['classifiers'])} total)",
            value="\n".join(info["classifiers"][:5]) +
            (f"\n... and {len(info['classifiers'])-5} more" if len(info["classifiers"]) > 5 else ""))
        if info["requires_dist"]:
            em.add_field(name=f"Requirements ({len(info['requires_dist'])} total)",
            value="\n".join(info["requires_dist"][:5]) +
            (f"\n... and {len(info['requires_dist'])-5} more" if len(info["requires_dist"]) > 5 else ""))

        await ctx.send(embed=em)

    @commands.command(name="strawpoll", description="Create a strawpoll")
    @commands.cooldown(3, 30, commands.BucketType.user)
    async def strawpoll(self, ctx, title=None, *options):
        if not title:
            options = []
            check = lambda message: message.channel == ctx.channel and message.author == ctx.author
            await ctx.send("What is the title of the poll?")
            message = await self.bot.wait_for("message", check=check)
            title = message.content

            await ctx.send("Send me a list of poll options. Type `done` to send the poll")
            while True:
                message = await self.bot.wait_for("message", check=check)
                if message.content == "done":
                    break
                options.append(message.content)
                await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

        data = {"poll": {"title": title, "answers": list(options)}}
        async with self.bot.session.post("https://strawpoll.com/api/poll", json=data, headers={"Content Type": "application/json"}) as resp:
            data = await resp.json()
        await ctx.send(f"https://strawpoll.com/{data['content_id']}")

def setup(bot):
    bot.add_cog(Internet(bot))
