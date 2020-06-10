from discord.ext import commands
from discord.ext import menus
import discord

from datetime import datetime as d
import inspect
import os
import asyncio
import functools
import aiohttp

from PIL import Image
from io import BytesIO

import io
import re
import zlib

class DocsPages(menus.ListPageSource):
    def __init__(self, data, search, ctx):
        self.search = search
        self.data = data
        self.ctx = ctx
        self.bot = ctx.bot
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        em = discord.Embed(title=f"Results for search '{self.search}'", description="", color=discord.Colour.from_rgb(*self.bot.customization[str(self.ctx.guild.id)]["color"]))
        for i, v in enumerate(entries, start=offset):
            em.description += "\n["+v[0]+"]("+v[1]+")"
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

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    
    
async def average_image_color(avatar_url, loop):
    async with aiohttp.ClientSession() as session:
        async with session.get(str(avatar_url)) as resp:
            data = await resp.read()
            image = BytesIO(data)

    partial = functools.partial(Image.open, image)
    img = await loop.run_in_executor(None, partial)

    partial = functools.partial(img.resize, (1, 1))
    img2 = await loop.run_in_executor(None, partial)

    partial = functools.partial(img2.getpixel, (0, 0))
    color = await loop.run_in_executor(None, partial)

    return(discord.Color(int("0x{:02x}{:02x}{:02x}".format(*color), 16)))

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

class Tools(commands.Cog):
    """Tools for discord."""
    def __init__(self, bot):
        self.bot = bot

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
            async with aiohttp.ClientSession().get(page + "/objects.inv") as resp:
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
        
        em = discord.Embed(title=f"Results for search '{obj}'", description="")
        for match in matches[:5]:
            em.description += "\n["+match[0]+"]("+match[1]+")"
        """await ctx.send(embed=em)"""
        pages = menus.MenuPages(source=DocsPages(matches, obj, ctx), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.group(name="docs", description="Get a link for docs on discord.py", usage="[object]", invoke_without_command=True)
    async def docs(self, ctx, obj=None):
        await self.do_docs(ctx, "latest", obj)

    @docs.command(name="py", description="Get a link for docs on python", usage="[object]")
    async def py_docs(self, ctx, obj=None):
        await self.do_docs(ctx, "python", obj)
    
    @commands.command(name="source", descriptin="Get source code for a specified command", usage="[command]")
    async def sourcecode(self, ctx, *, command):
        source_url = "https://github.com/ilovetocode2019/Robo-Coder"
        branch = "master"

        if command is None:
            return await ctx.send(source_url)
        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                return await ctx.send('Could not find command.')

            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            branch = 'master'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)


    @commands.cooldown(1, 20)
    @commands.group(name="github", description="Get infromation about a GitHub repository", usage="[username/repositpry]", invoke_without_command=True)
    async def github(self, ctx, repo):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/repos/{repo}") as response:
                data = await response.json()
        if data.get("message") == "Not Found":
            return await ctx.send("Repository not found")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/repos/{repo}/releases") as response:
                releases_data = await response.json()


        em = discord.Embed(title=data.get("name"), description=data.get("description"), url=data.get("html_url"), color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))
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


    @commands.cooldown(1, 20)
    @github.command(name="user", description="Get a GitHub user", usage="[user]")
    async def github_user(self, ctx, user):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/users/{user}") as response:
                data = await response.json()

        if data.get("message") == "Not Found":
            return await ctx.send("User not found")
        
        em = discord.Embed(title=data.get("login"), description=data.get("bio"), url=data.get("html_url"), color=discord.Colour.from_rgb(*self.bot.customization[str(ctx.guild.id)]["color"]))

        em.add_field(name="Repositories", value=data.get("public_repos"))
        em.add_field(name="Gists", value=data.get("public_gists"))
        em.add_field(name="Followers", value=data.get("followers"))
        em.add_field(name="Following", value=data.get("following"))
        
        if data.get("blog") != "":
            em.add_field(name="Blog", value=data.get("blog"))
        em.set_thumbnail(url=data.get("avatar_url"))
        await ctx.send(embed=em)




    @commands.command(name="purge", description="Delete a mass amount of messages", usage="[amount]", hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, *, arg):
        await ctx.send("Deleting " + str(arg) + " messages......")
        await asyncio.sleep(4)
        await ctx.channel.purge(limit=int(arg)+1)

    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild
        
        try:
            color = await average_image_color(guild.icon_url, self.bot.loop)
        except:
            color = discord.Embed.Empty
        em = discord.Embed(title=guild.name, description="", color=color)
        
        em.set_thumbnail(url=guild.icon_url)

        em.add_field(name="Owner", value=guild.owner.mention)

        em.add_field(name="ID", value=guild.id)

        em.add_field(name="Created at", value=str(guild.created_at))

        em.add_field(name="Channels", value=f"Text: {str(guild.member_count)}\nVoice: {str(len(guild.voice_channels))}")

        em.add_field(name="Members", value=len(guild.members))
        
        status = {"online":0, "idle":0, "dnd":0, "offline":0}
        for member in guild.members:
            status[str(member.status)] += 1
        em.add_field(name="Status List", value=f"Online {status['online']}\nIdle {status['idle']}\nDnd {status['dnd']}\nOffline {status['offline']}")

        await ctx.send(embed=em)

    @commands.command(name="userinfo", description="Get info on a user", usage="[member]")
    @commands.guild_only()
    async def userinfo(self, ctx, *, user:discord.Member=None):
        if not user:
            user = ctx.author

        if not user.nick:
            nick = ""
        else:
            nick = user.nick

        try:
            color = await average_image_color(user.avatar_url, self.bot.loop)
        except:
            color = discord.Embed.Empty
        em = discord.Embed(title=user.name, description=nick, color=color)
        
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n👑 This person owns the server"

        if user.bot:
            em.description += "\n🤖 This person is a bot"

        em.add_field(name="Created at", value=str(user.created_at))

        em.add_field(name="Joined at", value=str(user.joined_at))

        em.add_field(name="Roles", value=" ".join([role.mention for role in user.roles]))

        await ctx.send(embed=em)

    @commands.command(name="avatar", description="Get a users avatar")
    async def avatar(self, ctx, *, user:discord.Member=None):

        if user == None:
            user = ctx.author

        try:
            color = await average_image_color(user.avatar_url, self.bot.loop)
        except:
            color = discord.Embed.Empty
        em = discord.Embed(color=color)
        em.set_image(url=user.avatar_url)
        await ctx.send(embed=em)



def setup(bot):
    bot.add_cog(Tools(bot))