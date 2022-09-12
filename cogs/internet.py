import base64
import datetime
import functools
import io
import json
import os
import re
import typing
import zlib

import discord
from dateutil import parser
from discord import app_commands
from discord.ext import commands, menus
import googletrans
from lxml import etree
from PIL import Image

from .utils import formats

LANGUAGES = {
    "af": "afrikaans",
    "sq": "albanian",
    "am": "amharic",
    "ar": "arabic",
    "hy": "armenian",
    "az": "azerbaijani",
    "eu": "basque",
    "be": "belarusian",
    "bn": "bengali",
    "bs": "bosnian",
    "bg": "bulgarian",
    "ca": "catalan",
    "ceb": "cebuano",
    "ny": "chichewa",
    "zh-cn": "chinese (simplified)",
    "zh-tw": "chinese (traditional)",
    "co": "corsican",
    "hr": "croatian",
    "cs": "czech",
    "da": "danish",
    "nl": "dutch",
    "en": "english",
    "eo": "esperanto",
    "et": "estonian",
    "tl": "filipino",
    "fi": "finnish",
    "fr": "french",
    "fy": "frisian",
    "gl": "galician",
    "ka": "georgian",
    "de": "german",
    "el": "greek",
    "gu": "gujarati",
    "ht": "haitian creole",
    "ha": "hausa",
    "haw": "hawaiian",
    "iw": "hebrew",
    "he": "hebrew",
    "hi": "hindi",
    "hmn": "hmong",
    "hu": "hungarian",
    "is": "icelandic",
    "ig": "igbo",
    "id": "indonesian",
    "ga": "irish",
    "it": "italian",
    "ja": "japanese",
    "jw": "javanese",
    "kn": "kannada",
    "kk": "kazakh",
    "km": "khmer",
    "ko": "korean",
    "ku": "kurdish (kurmanji)",
    "ky": "kyrgyz",
    "lo": "lao",
    "la": "latin",
    "lv": "latvian",
    "lt": "lithuanian",
    "lb": "luxembourgish",
    "mk": "macedonian",
    "mg": "malagasy",
    "ms": "malay",
    "ml": "malayalam",
    "mt": "maltese",
    "mi": "maori",
    "mr": "marathi",
    "mn": "mongolian",
    "my": "myanmar (burmese)",
    "ne": "nepali",
    "no": "norwegian",
    "or": "odia",
    "ps": "pashto",
    "fa": "persian",
    "pl": "polish",
    "pt": "portuguese",
    "pa": "punjabi",
    "ro": "romanian",
    "ru": "russian",
    "sm": "samoan",
    "gd": "scots gaelic",
    "sr": "serbian",
    "st": "sesotho",
    "sn": "shona",
    "sd": "sindhi",
    "si": "sinhala",
    "sk": "slovak",
    "sl": "slovenian",
    "so": "somali",
    "es": "spanish",
    "su": "sundanese",
    "sw": "swahili",
    "sv": "swedish",
    "tg": "tajik",
    "ta": "tamil",
    "te": "telugu",
    "th": "thai",
    "tr": "turkish",
    "uk": "ukrainian",
    "ur": "urdu",
    "ug": "uyghur",
    "uz": "uzbek",
    "vi": "vietnamese",
    "cy": "welsh",
    "xh": "xhosa",
    "yi": "yiddish",
    "yo": "yoruba",
    "zu": "zulu"
}

PAGE_TYPES = {
    "latest": "https://discordpy.readthedocs.io/en/latest",
    "asyncpg": "https://magicstack.github.io/asyncpg/current/",
    "pillow": "https://pillow.readthedocs.io/en/latest",
    "tpy": "https://telegrampy.readthedocs.io/en/latest",
    "python": "https://docs.python.org/3"
}


class JumpBackView(discord.ui.View):
    def __init__(self, jump_url):
        super().__init__()
        self.add_item(discord.ui.Button(url=jump_url, label="Original Message"))

class GoogleResultPages(menus.ListPageSource):
    def __init__(self, entries, query):
        super().__init__(entries, per_page=1)

        self.entries = entries
        self.query = query

    async def format_page(self, menu, entry):
        em = discord.Embed(**entry, color=0x4285F3)
        em.set_author(name=f"Results for '{self.query}'")
        em.set_footer(text=f"{entry['url']} | Result {menu.current_page+1}/{len(self.entries)}")

        return em

class DocumentationPages(menus.ListPageSource):
    def __init__(self, entries, *, query):
        super().__init__(entries, per_page=10)

        self.entries = entries
        self.query = query

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        em = discord.Embed(title=f"Results for '{self.query}'", description="", color=0x96c8da)

        for counter, entry in enumerate(entries, start=offset):
            em.description += f"\n[`{entry[0]}`]({entry[1]})"

        em.set_footer(text=f"{len(self.entries)} results | Page {menu.current_page+1}/{int(len(self.entries)/10)+1}")

        return em

class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode("utf-8")

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if not chunk:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b""
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b"\n")
            while pos != -1:
                yield buf[:pos].decode("utf-8")
                buf = buf[pos + 1:]
                pos = buf.find(b"\n")

def finder(text, collection, *, key=None):
    suggestions = []
    text = str(text)
    pat = ".*?".join(map(re.escape, text))
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

    return [z for _, _, z in sorted(suggestions, key=sort_key)]

class Internet(commands.Cog):
    """Internet commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = ":globe_with_meridians:"

        self.translator = googletrans.Translator()
        self.translate_context_menu = app_commands.ContextMenu(name="Translate", callback=self.context_menu_translate)
        self.bot.tree.add_command(self.translate_context_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.translate_context_menu.name, type=self.translate_context_menu.type)

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != "# Sphinx inventory version 2":
            raise RuntimeError("Invalid objects.inv file version.")

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it"s a zlib header
        line = stream.readline()
        if "zlib" not in line:
            raise RuntimeError("Invalid objects.inv file, not z-lib compatible.")

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r"(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)")
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(":")
            if directive == "py:module" and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == "std:doc":
                subdirective = "label"

            if location.endswith("$"):
                location = location[:-1] + name

            key = name if dispname == "-" else dispname
            prefix = f"{subdirective}:" if domain == "std" else ""

            if projname == "discord.py":
                key = key.replace("discord.ext.commands.", "").replace("discord.", "")
            elif projname == "telegram.py":
                key = key.replace("telegrampy.ext.commands.", "").replace("telegrampy.", "")


            result[f"{prefix}{key}"] = os.path.join(url, location)

        return result

    async def build_docs_lookup_table(self):
        cache = {}
        for key, page in PAGE_TYPES.items():
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
        PAGE_TYPES = {
            "latest": "https://discordpy.readthedocs.io/en/latest",
            "asyncpg": "https://magicstack.github.io/asyncpg/current/",
            "pillow": "https://pillow.readthedocs.io/en/latest",
            "tpy": "https://telegrampy.readthedocs.io/en/latest",
            "python": "https://docs.python.org/3"
        }

        if obj is None:
            await ctx.send(PAGE_TYPES[key])
            return

        if not hasattr(self, "_docs_cache"):
            async with ctx.typing():
                await self.build_docs_lookup_table()

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

        matches = finder(obj, cache, key=lambda t: t[0])

        if not matches:
            return await ctx.send("Couldn't find anything.")

        if ctx.interaction or len(matches) <=  10:
            em = discord.Embed(title=f"Results for '{obj}'", description="", color=0x96c8da)

            for match in matches[:10]:
                em.description += f"\n[`{match[0]}`]({match[1]})"

            em.set_footer(text=f"Showing {len(matches[:10])}/{formats.plural(len(matches)):result}")

            await ctx.send(embed=em)
        else:
            pages = menus.MenuPages(source=DocumentationPages(matches, query=obj), clear_reactions_after=True)
            await pages.start(ctx)

    async def slash_docs_autocomplete(self, interaction, current):
        if not hasattr(self, "_docs_cache"):
            await self.build_docs_lookup_table()

        if not current:
            return []

        cache = list(self._docs_cache[interaction.command.name].items())
        matches = finder(current, cache, key=lambda t: t[0])[:10]
        return [app_commands.Choice(name=match[0], value=match[0]) for match in matches]

    @commands.command(name="google", description="Search google", aliases=["g"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def google(self, ctx, *, query):
        async with ctx.typing():
            params = {"q": query, "safe": "on", "lr": "lang_en", "hl": "en"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0"}

            # Request for search results page
            async with self.bot.session.get("https://google.com/search", params=params, headers=headers) as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to fetch google search results (status code {resp.status_code})")

                html = await resp.text("utf-8")

                # Debugging
                if ctx.author.id == self.bot.owner_id:
                    with open("google.html", "w", encoding="utf-8") as file:
                        file.write(html)

                root = etree.fromstring(html, etree.HTMLParser())

            # Search results
            results = [g.find(".//div[@class='tF2Cxc']") for g in root.findall(".//div[@class='g']")]
            if results and results[0] == results[1]:
                results = results[1:]

            entries = []

            # Parse results
            for result in results:
                if result is not None:
                    link = result.find(".//div[@class='yuRUbf']/a")

                    href = link.get("href")
                    h3 = link.find(".//h3[@class='LC20lb MBeuO DKV0Md']")
                    cite = link.find(".//cite[@role='text']")

                    preview = result.find(".//div[@class='VwiC3b yXK7lf MUxGbd yDYNvb lyLwlc lEBKkf']")
                    entries.append({"title": h3.text, "description": f"`{cite.text}` \n\n{' '.join(preview.itertext()) if preview is not None else 'No information is available for this page.'}", "url": href})

            """# Format results
            search_results = "\n".join([f"[{result['title']}]({result['url']})" for result in entries[:5]])

            if not search_results.strip():
                search_results = "No search results found."

            # Calculation card
            calculator = root.find(".//div[@class='tyYmIf']")
            if calculator is not None:
                equation = calculator.find(".//span[@class='vUGUtc']")
                result = calculator.find(".//span[@class='qv3Wpe']")

                em = discord.Embed(title="Calculator", description=f"{equation.text}{result.text}", color=0x4285F3)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Conversion card
            converter = root.find(".//div[@class='vk_c card obcontainer card-section']")
            if converter is not None:
                src, dest = converter.findall(".//input[@class='vXQmIe gsrt']")
                units = converter.findall(".//option[@selected='1']")
                formula = converter.find(".//div[@class='bjhkR']")

                em = discord.Embed(title=f"{units[0].text} Converter", color=0x4285F3)
                em.add_field(name=units[1].text.title(), value=src.get("value"))
                em.add_field(name=units[2].text.title(), value=dest.get("value"))
                em.add_field(name="Formula", value=formula.text.capitalize())

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Currency card
            currency_converter = root.find(".//table[@class='qzNNJ']")
            if currency_converter is not None:
                src_name, dest_name = currency_converter.findall(".//option[@selected='1']")
                src = currency_converter.find(".//input[@class='ZEB7Fb vk_gy vk_sh Hg3mWc']")
                dest = currency_converter.find(".//input[@class='a61j6 vk_gy vk_sh Hg3mWc']")
                time = root.find(".//div[@class='hqAUc']/span")

                em = discord.Embed(title="Currency Converter", description=time.text.replace("·", ""), color=0x4285F3)
                em.add_field(name=f"{src_name.text} ({src_name.get('value')})", value=src.get("value"))
                em.add_field(name=f"{dest_name.text} ({dest_name.get('value')})", value=dest.get("value"))

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Generic information card
            information = root.find(".//div[@class='IZ6rdc']")
            if information is not None:
                em = discord.Embed(title="Information", description=f"{information.text}", color=0x4285F3)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Translation card
            translator = root.find(".//div[@class='tw-src-ltr']")
            if translator is not None:
                src_lang = root.find(".//span[@class='source-language']")
                dest_lang = root.find(".//span[@class='target-language']")

                src = translator.find(".//pre[@id='tw-source-text']/span")
                dest = translator.find(".//pre[@id='tw-target-text']/span")

                em = discord.Embed(title="Translator", color=0x4285F3)
                em.add_field(name=src_lang.text.title(), value=src.text)
                em.add_field(name=dest_lang.text.title(), value=dest.text)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Time in card
            time_in = root.find(".//div[@class='gsrt vk_bk dDoNo FzvWSb XcVN5d DjWnwf']")
            if time_in is not None:
                date = root.find(".//div[@class='vk_gy vk_sh']")
                location = root.find(".//span[@class='vk_gy vk_sh']")

                em = discord.Embed(title=location.text, description=f"{time_in.text} — {''.join(date.itertext())}", color=0x4285F3)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Generic time card
            generic_time = root.find(".//div[@class='vk_c vk_gy vk_sh card-section sL6Rbf R36Kq']")
            if generic_time is not None:
                info = generic_time.find(".//div")

                em = discord.Embed(title="Time", description="".join(info.itertext()), color=0x4285F3)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Definition card
            definer = root.find(".//div[@class='WI9k4c']")
            if definer is not None:
                word = definer.find(".//div[@class='RjReFf jY7QFf']/div[@class='DgZBFd XcVN5d frCXef']/span")
                pronounciation = definer.find(".//div[@class='S23sjd g30o5d']")
                word_type = root.find(".//div[@class='pgRvse vdBwhd ePtbIe']/i/span")

                raw_examples = [raw_example for raw_example in root.findall(".//div[@class='L1jWkf h3TRxf']/div/span") if raw_example.text]
                examples = [f"{counter+1}. {example.text}" for counter, example in enumerate(raw_examples)]

                em = discord.Embed(title="Definition", description=f"{word.text} `{''.join(pronounciation.itertext())}`\n\n*{word_type}*", color=0x4285F3)
                em.add_field(name="Examples", value="\n".join(examples))

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)

                return await ctx.send(embed=em)

            # Weather card
            weather = root.find(".//div[@class='nawv0d']")
            if weather is not None:
                image = weather.find(".//img[@class='wob_tci']")
                temperature_f = weather.find(".//span[@class='wob_t TVtOme']")
                temperature_c = weather.find(".//span[@class='wob_t']")

                location = weather.find(".//div[@class='wob_loc mfMhoc']")
                time = weather.find(".//div[@class='wob_dts']")

                details = weather.find(".//div[@class='wtsRwe']")
                precipitation = details.find(".//span[@id='wob_pp']")
                humidity = details.find(".//span[@id='wob_hm']")
                wind = details.find(".//span[@class='wob_t']")

                em = discord.Embed(title=f"Weather in {location.text}", description=f"{time.text} — {image.get('alt')}", color=0x4285F3)
                em.set_thumbnail(url=f"https:{image.get('src')}")
                em.add_field(name="Temperature", value=f"{temperature_f.text}°F | {temperature_c.text}°C", inline=False)
                em.add_field(name="Precipitation", value=precipitation.text)
                em.add_field(name="Humidity", value=humidity.text)
                em.add_field(name="Wind", value=wind.text)

                if search_results:
                    em.add_field(name="Search Results", value=search_results, inline=False)
                

                return await ctx.send(embed=em)"""

            if not results:
                return await ctx.send("No results found.")

        pages = menus.MenuPages(GoogleResultPages(entries, query), clear_reactions_after=True)
        await pages.start(ctx)

    @commands.hybrid_command(name="translate", description="Translate something using google translate")
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def translate(self, ctx, *, query: str):
        async with ctx.typing():
            partial = functools.partial(self.translator.translate, query)
            translated = await self.bot.loop.run_in_executor(None, partial)

            src_lang = LANGUAGES.get(translated.src.lower(), "???").title()
            dest_lang = LANGUAGES.get(translated.dest.lower(), "???").title()

            em = discord.Embed(title="Translator", color=0x4285F3)
            em.add_field(name=f"From {src_lang}", value=query)
            em.add_field(name=f"To {dest_lang}", value=translated.text, inline=False)

        await ctx.send(embed=em)

    async def context_menu_translate(self, interaction, message: discord.Message):
        if not message.content:
            return await interaction.response.send_message("There is no text to translate in this message.", ephemeral=True)

        partial = functools.partial(self.translator.translate, message.content)
        translated = await self.bot.loop.run_in_executor(None, partial)

        src_lang = LANGUAGES.get(translated.src.lower(), "???").title()
        dest_lang = LANGUAGES.get(translated.dest.lower(), "???").title()

        em = discord.Embed(title="Translator", color=0x4285F3)
        em.add_field(name=f"From {src_lang}", value=message.content)
        em.add_field(name=f"To {dest_lang}", value=translated.text, inline=False)

        await interaction.response.send_message(embed=em, view=JumpBackView(message.jump_url), ephemeral=True)

    @commands.hybrid_command(name="wikipedia", description="Search wikipedia", aliases=["wiki"])
    @commands.cooldown(2, 20, commands.BucketType.user)
    async def wikipedia(self, ctx, *, search):
        async with ctx.typing():
            url = "http://en.wikipedia.org/w/api.php"
            data = {"prop": "info|pageprops", "inprop": "url", "ppprop": "disambiguation", "redirects": "", "titles": search, "format": "json", "action": "query"}

            async with self.bot.session.get(url, params=data) as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to fetch page data (error code {resp.status}).")

                page_data = await resp.json()
                pages = page_data["query"]["pages"]
                page_id = list(page_data["query"]["pages"].keys())[0]
                page = pages[page_id]
                if "pageid" not in page:
                    return await ctx.send(f"Couldn't find a page with the name '{search}'")

            data = {"prop": "extracts", "explaintext": "", "pageids": page_id, "format": "json", "action": "query"}
            async with self.bot.session.get(url, params=data) as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to fetch page data (error code {resp.status}).")
                summary_data = await resp.json()
                summary = summary_data["query"]["pages"][page_id]["extract"]

        summary = summary.replace("===", "__")
        summary = summary.replace("==", "**")
        description = f"{summary[:1000]}{'...' if len(summary) > 1000 else ''}\n\n[Read more]({page['fullurl']})"

        em = discord.Embed(title=f"{page['title']}", description=description, url=page["fullurl"], color=0x96c8da)
        await ctx.send(embed=em)

    @commands.hybrid_group(name="docs", fallback="latest", description="Search the discord.py docs", invoke_without_command=True)
    @app_commands.autocomplete(obj=slash_docs_autocomplete)
    async def docs(self, ctx, *, obj: typing.Optional[str]):
        await self.do_docs(ctx, "latest", obj)

    @docs.command(name="python", description="Search the python docs", aliases=["py"])
    @app_commands.autocomplete(obj=slash_docs_autocomplete)
    async def docs_python(self, ctx, *, obj: typing.Optional[str]):
        await self.do_docs(ctx, "python", obj)

    @docs.command(name="telegram", with_app_command=False, description="Search the telegram.py docs", aliases=["telegrampy", "telegram.py", "tpy"], hidden=True)
    async def docs_telegram(self, ctx, *, obj: typing.Optional[str]):
        await self.do_docs(ctx, "tpy", obj)

    @commands.hybrid_command(name="api", description="Search the Discord API docs", aliases=["dapi", "discord"])
    async def api(self, ctx, *, obj: typing.Optional[str]):
        if not obj:
            return await ctx.send("https://discord.com/developers/docs/intro")

        async with ctx.typing():
            if not hasattr(self, "_api_docs"):
                self._api_docs = await self.build_api_docs()

            matches = finder(obj, self._api_docs, key=lambda t: t[0])

        if not matches:
            return await ctx.send("Couldn't find anything.")

        if ctx.interaction or len(matches) <= 10:
            em = discord.Embed(title=f"Results for '{obj}'", description="", color=0x96c8da)

            for match in matches[:10]:
                em.description += f"\n[`{match[0]}`]({match[1]})"

            em.set_footer(text=f"Showing {len(matches[:10])}/{formats.plural(len(matches)):result}")

            await ctx.send(embed=em)
        else:
            pages = menus.MenuPages(DocumentationPages(matches, query=obj), clear_reactions_after=True)
            await pages.start(ctx)

    @api.autocomplete("obj")
    async def slash_api_docs_autocomplete(self, interaction, current):
        if not hasattr(self, "_api_docs"):
            self._api_docs = await self.build_api_docs()

        if not current:
            return []

        matches = finder(current, self._api_docs, key=lambda t: t[0])[:10]
        return [app_commands.Choice(name=match[0], value=match[0]) for match in matches]

    @commands.hybrid_command(name="faq", description="Search the discord.py faq")
    async def faq(self, ctx, *, query: typing.Optional[str]):
        if not query:
            return await ctx.send("https://discordpy.readthedocs.io/en/latest/faq.html")

        async with ctx.typing():
            if not hasattr(self, "_faq_entries"):
                self._faq_entries = await self.build_faq_entries()

            matches = finder(query, self._faq_entries, key=lambda entry: entry[0])

        if not matches:
            return await ctx.send("Couldn't find anything.")

        if ctx.interaction or len(matches) <= 10:
            em = discord.Embed(title=f"Results for '{query}'", description="", color=0x96c8da)

            for match in matches[:10]:
                em.description += f"\n[`{match[0]}`]({match[1]})"

            em.set_footer(text=f"Showing {len(matches[:10])}/{formats.plural(len(matches)):result}")

            await ctx.send(embed=em)
        else:
            pages = menus.MenuPages(DocumentationPages(matches, query=obj), clear_reactions_after=True)
            await pages.start(ctx)

    @faq.autocomplete("query")
    async def slash_faq_autocomplete(self, interaction, current):
        if not hasattr(self, "_faq_entries"):
            self._faq_entries = await self.build_faq_entries()

        if not current:
            return []

        matches = finder(current, self._faq_entries, key=lambda t: t[0])[:10]
        return [app_commands.Choice(name=match[0], value=match[0]) for match in matches]

    @commands.hybrid_command(name="roblox", description="Get info on a Roblox user")
    @commands.cooldown(2, 20, commands.BucketType.user)
    async def roblox(self, ctx, username):
        # Because of how the Roblox API is structured
        # We have to get data from the user profile html page
        # And make requests to multiple API endpoints

        async with ctx.typing():
            params = {"username": username}
            # Search for user
            async with self.bot.session.get(f"https://api.roblox.com/users/get-by-username", params=params) as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to find user (error code {resp.status}).")

                profile = await resp.json()
                if "Id" not in profile:
                    return await ctx.send("Roblox user not found.")

                user_id = profile["Id"]
                base_url = f"https://www.roblox.com/users/{user_id}"

            # Fetch user info that the API provides
            async with self.bot.session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to fetch user data from users.roblox.com (error code {resp.status}).")

                user_data = await resp.json()

                if user_data["isBanned"]:
                    return await ctx.send("This Roblox user is banned.")

            # Get information about the user from the website profile page
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0"}
            async with self.bot.session.get(f"{base_url}/profile", headers=headers) as resp:
                if resp.status != 200:
                    return await ctx.send(f"Failed to fetch user data (error code {resp.status}).")

                html = await resp.text("utf-8")

                # Debugging
                with open("roblox.html", "w", encoding="utf-8") as file:
                    file.write(html)

                root = etree.fromstring(html, etree.HTMLParser())

            premium = root.find(".//span[@class='icon-premium-medium']")
            about = root.find(".//span[@class='profile-about-content-text linkify']")
            details = root.find(".//div[@class='hidden']")
            display_name = root.find(".//div[@class='profile-display-name font-caption-body text text-overflow']")

            em = discord.Embed(title=f"{'<:roblox_premium:809089466056310834> ' if premium is not None else ''}{display_name.text.strip()}", description="", url=f"{base_url}/profile", color=0x96c8da)
            em.set_author(name=f"@{profile['Username']}")
            em.set_thumbnail(url=f"https://www.roblox.com/bust-thumbnail/image?userId={profile['Id']}&width=420&height=420&format=png")
            em.set_thumbnail(url=f"https://www.roblox.com/outfit-thumbnail/image?userOutfitId={profile['Id']}&width=420&height=420&format=png")
            em.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={profile['Id']}&width=420&height=420&format=png")
            em.set_footer(text=f"ID: {profile['Id']}")

            if about is not None:
                em.description += about.text

            friends_count = details.get("data-friendscount")
            if friends_count:
                url = f"{base_url}/friends#!/friends"
                em.add_field(name="Friends", value=f"{friends_count} [(view)]({url})")

            followers_count = details.get("data-followerscount")
            if followers_count:
                url = f"{base_url}/friends#!/followers"
                em.add_field(name="Followers", value=f"{followers_count} [(view)]({url})")

            followings_count = details.get("data-followingscount")
            if followings_count:
                url = f"{base_url}/friends#!/following"
                em.add_field(name="Following", value=f"{followings_count} [(view)]({url})")

            status = details.get("data-statustext")
            if status:
                em.add_field(name="Status", value=status, inline=False)

            on_website = root.find(".//span[@class='avatar-status online profile-avatar-status icon-online']")
            in_game = root.find(".//span[@class='avatar-status game icon-game profile-avatar-status']")

            if on_website is not None:
                em.add_field(name="Presence", value="Website", inline=False)
            elif in_game is not None:
                em.add_field(name="Presence", value="Game", inline=False)
            else:
                em.add_field(name="Presence", value="Offline", inline=False)


            created_at = parser.isoparse(user_data["created"])
            em.add_field(name="Created At", value=created_at.strftime('%m/%d/%Y'))

        await ctx.send(embed=em)

    @commands.hybrid_command(name="minecraft", description="Get info on a Minecraft user", aliases=["mc"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def minecraft(self, ctx, username):
        async with ctx.typing():
            async with self.bot.session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as resp:
                if resp.status != 200:
                    return await ctx.send("I couldn't find that user.")

                data = await resp.json()

            name = data["name"]
            uuid = data["id"]

            async with self.bot.session.get(f"https://api.mojang.com/user/profiles/{uuid}/names") as resp:
                name_history = await resp.json()

            names = []
            for name_data in reversed(name_history):
                timestamp = name_data.get("changedToAt")
                old_name = discord.utils.escape_markdown(name_data["name"])

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

            em = discord.Embed(title=name, color=0x96c8da)
            em.set_thumbnail(url="attachment://face.png")
            em.add_field(name="Names", value="\n".join(names))
            em.set_footer(text=f"ID: {uuid}")

        await ctx.send(embed=em, file=discord.File(output, filename="face.png"))

    @commands.hybrid_command(name="github", description="Get info on a GitHub item", aliases=["gh"])
    @commands.cooldown(3, 20, commands.BucketType.user)
    async def github(self, ctx, item):
        headers = {"Authorization": f"token {self.bot.config.github_token}"} if getattr(self.bot.config, "github_token", None) else None

        async with ctx.typing():
            if "/" in item:
                async with self.bot.session.get(f"https://api.github.com/repos/{item}", headers=headers) as resp:
                    if resp.status != 200:
                        return await ctx.send("I couldn't find that GitHub repository.")

                    data = await resp.json()
                    owner = data["owner"]

                em = discord.Embed(title=data["full_name"], description=f"{data['description'] or ''}\n{data['homepage'] or ''}", url=data["html_url"], timestamp=parser.isoparse(data["created_at"]), color=0x96c8da)
                em.set_author(name=owner["login"], url=owner["html_url"], icon_url=owner["avatar_url"])
                em.set_thumbnail(url=owner["avatar_url"])
                em.add_field(name="Language", value=data["language"])
                em.add_field(name="Stars", value=data["stargazers_count"])
                em.add_field(name="Watching", value=data["watchers_count"])
                em.add_field(name="Forks", value=data["forks_count"])
                em.set_footer(text="Created")
            else:
                async with self.bot.session.get(f"https://api.github.com/users/{item}", headers=headers) as resp:
                    if resp.status != 200:
                        return await ctx.send("I couldn't find that GitHub user.")
                    data = await resp.json()

                em = discord.Embed(title=data["login"], description=data["bio"], url=data["html_url"], timestamp=parser.isoparse(data["created_at"]), color=0x96c8da)
                em.set_thumbnail(url=data["avatar_url"])
                em.add_field(name="Repositories", value=data["public_repos"])
                em.add_field(name="Gists", value=data["public_gists"])
                em.add_field(name="Followers", value=data["followers"])
                em.add_field(name="Following", value=data["following"])
                if data["blog"]:
                    em.add_field(name="Website", value=data["blog"])
                em.set_footer(text="Created")

        await ctx.send(embed=em)

    @commands.hybrid_command(name="pypi", description="Search for a project on PyPI", aliases=["pip", "project"])
    @commands.cooldown(3, 20, commands.BucketType.user)
    async def pypi(self, ctx, project, release: typing.Optional[str]):
        async with ctx.typing():
            if release:
                url = f"https://pypi.org/pypi/{project}/{release}/json"
            else:
                url = f"https://pypi.org/pypi/{project}/json"

            async with self.bot.session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send(f"I couldn't find that package.")

                data = await resp.json()
                info = data["info"]
                releases = data["releases"] if not release else None

        em = discord.Embed(title=f"{info['name']} {info['version']}", description=info["summary"], url=info["package_url"], color=0x96c8da)
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
            value="\n".join([f"[{release}]({info['package_url']}{release})" for release in list(reversed(list(releases.keys())))[:5]]) +
            (f"\n... and {len(releases)-5} more" if len(releases) > 5 else ""))
        if info["project_urls"]:
            em.add_field(name=f"Project Links ({len(info['project_urls'])} total)",
            value="\n".join([f"[{item[0]}]({item[1]})" for item in list(info["project_urls"].items())[:5]]) +
            (f"\n... and {len(info['project_urls'])-5} more" if len(info["project_urls"]) > 5 else ""))
        if info["requires_dist"]:
            em.add_field(name=f"Requirements ({len(info['requires_dist'])} total)",
            value="\n".join(info["requires_dist"][:5]) +
            (f"\n... and {len(info['requires_dist'])-5} more" if len(info["requires_dist"]) > 5 else ""),
            inline=False)

        await ctx.send(embed=em)

    @commands.command(name="strawpoll", description="Create a strawpoll")
    @commands.cooldown(3, 20, commands.BucketType.user)
    async def strawpoll(self, ctx, title=None, *options):
        if not title:
            options = []
            check = lambda message: message.channel == ctx.author.dm_channel and message.author == ctx.author
            try:
                await ctx.author.send("What is the title of the poll?")
            except discord.Forbidden:
                return await ctx.send(":x: You have DMs disabled")

            message = await self.bot.wait_for("message", check=check)
            title = message.content

            await ctx.author.send("Send me a list of poll options. Type `done` to send the poll")
            while True:
                message = await self.bot.wait_for("message", check=check)

                if message.content == "done":
                    break
                elif message.content == "abort":
                    return await ctx.author.send("Aborting")

                options.append(message.content)
                await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

        if len(options) < 2:
            return await ctx.send(":x: You must have at least 2 options")

        async with ctx.typing():
            data = {"poll": {"title": title, "answers": list(options)}}
            async with self.bot.session.post("https://strawpoll.com/api/poll", json=data, headers={"Content Type": "application/json"}) as resp:
                data = await resp.json()

        await ctx.send(f"https://strawpoll.com/{data['content_id']}")

    async def build_faq_entries(self):
        """Builds the discord.py faq entries."""

        faq_url = "https://discordpy.readthedocs.io/en/latest/faq.html"

        entries = {}
        async with self.bot.session.get(faq_url) as resp:
            html = await resp.text("utf-8")
            root = etree.fromstring(html, etree.HTMLParser())
            questions = root.findall(".//ul[@class='simple']/li/ul//a")

            for question in questions:
                entries["".join(question.itertext()).strip()] = f"{faq_url}{question.get('href').strip()}"

        return list(entries.items())

    async def build_api_docs(self):
        """Builds the Discord API docs."""

        headers = {"Authorization": f"token {self.bot.config.github_token}"} if getattr(self.bot.config, "github_token", None) else None

        async with self.bot.session.get("https://api.github.com/repos/discord/discord-api-docs/contents/docs", headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"GitHub returned the status code {resp.status}")

            data = await resp.json()
            pages = await self.fetch_api_docs(data)

        # My attempt at parsing the Discord API Docs
        entries = []

        for title, page in pages.items():
            is_codeblock = False
            last_header = None

            for line in page.split("\n"):
                # Check for codeblocks and headers
                is_codeblock = line.startswith("```") if not is_codeblock else not line.startswith("```")
                is_subheader = line.startswith(("# ", "## ", "### ", "#### ", "##### ", "###### ")) and not is_codeblock

                if is_subheader:
                    header, text = line.split(" ", 1)

                    # DELETE WEBHOOK MESSAGE is a h1 ¯\_(ツ)_/¯
                    if is_subheader and " % " in text and len(header) <= 2:
                        text = text.split(" % ")[0]
                    elif len(header) == 1:
                        last_header = text

                    section = text

                    # Properly label and link tables/codeblocks
                    if len(header) == 6:
                        text = f"Table: {text}"
                        section = f"{last_header} {section}"

                    # Format entry
                    section = section.replace(":", "").replace(".", "").replace("?", "").replace("-", "").replace("_", "").replace(" ", "-").lower()
                    link = f"https://discord.com/developers/{title.replace('_', '-').lower()}#{section}"
                    entries.append((text, link))

        return entries

    async def fetch_api_docs(self, files):
        """Fetch the Discord API docs."""

        pages = {}

        for file in files:
            if file["download_url"]:
                async with self.bot.session.get(file["download_url"]) as resp:
                    markdown = await resp.text("utf-8")

                    path = file["path"]
                    path = path[:-3]
                    pages[path] = markdown

            else:
                headers = {"Authorization": f"token {self.bot.config.github_token}"} if getattr(self.bot.config, "github_token", None) else None

                async with self.bot.session.get(f"https://api.github.com/repos/discord/discord-api-docs/contents/{file['path']}", headers=headers) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"GitHub returned the status code {resp.status}")

                    data = await resp.json()
                    docs = await self.fetch_api_docs(data)
                    pages.update(docs)

        return pages

async def setup(bot):
    await bot.add_cog(Internet(bot))
