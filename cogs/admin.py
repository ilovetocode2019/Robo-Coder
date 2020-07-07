from discord.ext import commands
import discord

import traceback
import sys
import os
import datetime

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id

    @commands.command(name="reload", description="Reload an extension", usage="[cog]")
    @commands.is_owner()
    async def _reload(self, ctx, cog="all"):
        if cog == "all":
            msg = ""

            for ext in self.bot.cogs_to_add:
                try:
                    self.bot.reload_extension(ext)
                    msg += f"**:repeat: Reloaded** `{ext}`\n\n"
                    print(f"Extension '{cog.lower()}' successfully reloaded.")

                except Exception as e:
                    traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
                    msg += (f"**:warning: Extension `{ext}` not loaded.**\n"
                            f"```py\n{traceback_data}```\n\n")
                    print(f"Extension 'cogs.{cog.lower()}' not loaded.\n"
                                     f"{traceback_data}")
            return await ctx.send(msg)

        try:
            self.bot.reload_extension(cog.lower())
            await ctx.send(f"**:repeat: Reloaded** `{cog.lower()}`")
            print(f"Extension '{cog.lower()}' successfully reloaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not reloaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not reloaded.\n{traceback_data}")

    @commands.command(name="load", description="Load an extension", usage="[cog]")
    @commands.is_owner()
    async def _load(self, ctx, cog):
        try:
            self.bot.load_extension(cog.lower())
            await ctx.send(f"**:white_check_mark: Loaded** `{cog.lower()}`")
            print(f"Extension '{cog.lower()}' successfully loaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not loaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog.lower()}' not loaded.\n{traceback_data}")

    @commands.command(name="unload", description="Unload an extension", usage="[cog]")
    @commands.is_owner()
    async def _unload_cog(self, ctx, cog):
        try:
            self.bot.unload_extension(cog)
            await ctx.send(f"**:x: Unloaded extension ** `{cog}`")
            print(f"Extension '{cog}' successfully unloaded.")
        except Exception as e:
            traceback_data = ''.join(traceback.format_exception(type(e), e, e.__traceback__, 1))
            await ctx.send(f"**:warning: Extension `{cog.lower()}` not unloaded.**\n```py\n{traceback_data}```")
            print(f"Extension 'cogs.{cog}' not unloaded.\n{traceback_data}")

    @commands.command(name="logout", description="Logout command")
    @commands.is_owner()
    async def logout(self, ctx):
        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "offline", int(timestamp))

        await self.bot.db.close()
        await self.bot.session.close()
        print("Logging out of Discord.")
        await ctx.send(":wave: Logging out.")
        await self.bot.logout()

    @commands.command(name="restart", description="Restart command")
    @commands.is_owner()
    async def restart(self, ctx):
        timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        await self.bot.db.execute("INSERT INTO status_updates (userid, status, time) VALUES ($1, $2, $3)", str(self.bot.user.id), "offline", int(timestamp))

        try:
            await self.bot.db.close()
        except:
            pass
        print("Logging out of Discord and restarting")
        await ctx.send("Restarting...")
        os.startfile("bot.py")
        await self.bot.logout()



def setup(bot):
    bot.add_cog(Admin(bot))