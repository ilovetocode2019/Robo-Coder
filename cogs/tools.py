from discord.ext import commands
import discord

from datetime import datetime as d
import inspect
import os
import asyncio
import aiohttp

def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    
    

class Tools(commands.Cog):
    """A bunch of tools you can use on your server."""
    def __init__(self, bot):
        self.bot = bot
    
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


        em = discord.Embed(title=data.get("name"), description=data.get("description"), url=data.get("html_url"), color=0x00ff00)
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

    @github.command(name="user", description="Get a GitHub user", usage="[user]")
    async def github_user(self, ctx, user):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/users/{user}") as response:
                data = await response.json()

        if data.get("message") == "Not Found":
            return await ctx.send("User not found")
        
        em = discord.Embed(title=data.get("login"), description=data.get("bio"), url=data.get("html_url"), color=0x00ff00)

        em.add_field(name="Repositories", value=data.get("public_repos"))
        em.add_field(name="Gists", value=data.get("public_gists"))
        em.add_field(name="Followers", value=data.get("followers"))
        em.add_field(name="Following", value=data.get("following"))
        
        if data.get("blog") != "":
            em.add_field(name="Blog", value=data.get("blog"))
        em.set_thumbnail(url=data.get("avatar_url"))
        await ctx.send(embed=em)




    @commands.command(name="purge", description="Delete a mass amount of meesages", usage="[amount]", hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, *, arg):
        await ctx.send("Deleting " + str(arg) + " messages......")
        await asyncio.sleep(4)
        await ctx.channel.purge(limit=int(arg)+1)

    @commands.command(name="serverinfo", description="Get info on the server", aliases=["guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild

        em = discord.Embed(title=guild.name, description="", color=0x00ff00)
        
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
    async def userinfo(self, ctx, user:discord.Member=None):
        if not user:
            user = ctx.author

        if not user.nick:
            nick = ""
        else:
            nick = user.nick
        em = discord.Embed(title=user.name, description=nick, color=0x00ff00)
        
        em.set_thumbnail(url=user.avatar_url)

        if user.id == ctx.guild.owner.id:
            em.description += "\n👑 This person owns the server"

        if user.bot:
            em.description += "\n🤖 This person is a bot"

        em.add_field(name="Created at", value=str(user.created_at))

        em.add_field(name="Joined at", value=str(user.joined_at))

        em.add_field(name="Roles", value=" ".join([role.mention for role in user.roles]))

        await ctx.send(embed=em)

    @commands.Cog.listener("on_member_update")
    async def on_member_update(self, before, after):
        if before.status != after.status:
            print(str(after.status))
            timestamp = d.now().timestamp()
            await self.bot.db.execute(f'''INSERT INTO Status_Updates(Userid, Status, Time) VALUES ($1, $2, $3)''', str(before.id), str(after.status), int(timestamp))

    @commands.command(name="status", description="Get an overall status of a user", usage="[user]")
    async def status(self, ctx, user: discord.Member=None):
        if not user:
            user = ctx.author

        rows = await self.bot.db.fetch(f"SELECT Status, Time FROM Status_Updates WHERE Status_Updates.Userid='{user.id}';")
        if len(rows) == 0:
            rows = [[str(user.status), int(d.now().timestamp())]]

        counter = 0
        status = {"online":0, "idle":0, "dnd":0, "offline":0}
        for row in rows:
            if len(rows)-1 > counter:
                status[row[0]] += rows[counter+1][1]-row[1]
            else:
                status[row[0]] += d.now().timestamp()-row[1]

            counter += 1
        
        total = status["online"] + status["idle"] + status["dnd"] + status["offline"]

        em = discord.Embed(title=user.name, color=0x00FF00)
        em.add_field(name="Online", value=status["online"]/total*100)
        em.add_field(name="Idle", value=status["idle"]/total*100)
        em.add_field(name="Do Not Disturb", value=status["dnd"]/total*100)
        em.add_field(name="Offline", value=status["offline"]/total*100)
        em.set_thumbnail(url=user.avatar_url)

        await ctx.send(embed=em)
                



def setup(bot):
    bot.add_cog(Tools(bot))