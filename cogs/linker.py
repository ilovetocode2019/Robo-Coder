from discord.ext import commands
import discord

class Session:
    """Represents a session with another channel"""

    def __init__(self, channel, webhook):
        self.channel = channel
        self.webhook = webhook
        self.messages = {}

class DMSession:
    """Represents a sesion bettwen the bot owner and a bot user"""
    
    def __init__(self, channel):
        self.channel = channel
        self.messages = {}

class Linker(commands.Cog):
    """Linking two channels together"""

    def __init__(self, bot):
        self.bot = bot
        self.linked = {}
        self.dm_sessions = {}
    
    @commands.has_permissions(manage_channels=True)
    @commands.group(name="link", description="Links a channel to another channel", usage="[channel id]", invoke_without_command=True)
    async def link(self, ctx, channel):
        channel = channel.strip("<#>")
        
        if not channel.isdigit():
            return await ctx.send("❌ That channel does not exist")
        if int(channel) == ctx.channel.id:
            return await ctx.send("❌ You cannot link to the current channel")
        if self.linked.get(int(channel)) or self.linked.get(ctx.channel.id):
            return await ctx.send("❌ A session is already going")

        channel = self.bot.get_channel(int(channel))
        
        if not channel:
            return await ctx.send("❌ That channel does not exist")
        if ctx.author.id not in [x.id for x in channel.members]:
            return await ctx.send("❌ You are not in that channel")
        if not channel.guild.get_member(ctx.author.id).guild_permissions.manage_webhooks:
            return await ctx.send("❌ You do not have manage messages in that server")

        if "Linked Channel" not in [x.name for x in (await channel.webhooks())]:
            await channel.create_webhook(name="Linked Channel")

        if "Linked Channel" not in [x.name for x in (await ctx.channel.webhooks())]:
            await ctx.channel.create_webhook(name="Linked Channel")
        
        self.linked[ctx.channel.id] = Session(channel.id, discord.utils.get((await channel.webhooks()), name="Linked Channel"))
        self.linked[channel.id] = Session(ctx.channel.id, discord.utils.get((await ctx.channel.webhooks()), name="Linked Channel"))

        await ctx.send("✅ Linked to the channel")

    @link.command(name="stop", description="Stops a link bettwen two channels")
    async def link_stop(self, ctx):
        session = self.linked.get(ctx.channel.id)

        if not session:
            return await ctx.send("❌ This channel in not currently linked")
        
        self.linked.pop(ctx.channel.id)
        await ctx.send("✅ Unlinked from the channel")
        self.linked.pop(session.channel)
        await self.bot.get_channel(session.channel).send("✅ Unlinked from the channel")

    @commands.group(name="dm", description="Creates a DM session with a user", usage="[user]", invoke_without_command=True)
    @commands.guild_only()
    @commands.is_owner()
    async def dm_command(self, ctx, *, user: discord.Member):
        if not user.dm_channel:
            await user.create_dm()

        if user.dm_channel.id in self.dm_sessions:
            return await ctx.send("❌ A DM session is already going with this user")

        if ctx.channel.id in self.dm_sessions:
           return await ctx.send("❌ A DM session is already going in this channel")

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await ctx.guild.create_text_channel(name=f"dm-{user}", overwrites=overwrites)

        self.linked[channel.id] = DMSession(user.dm_channel.id)
        self.linked[user.dm_channel.id] = DMSession(channel.id)

        await ctx.send("✅ Created a DM session")

    @dm_command.command(name="stop", description="Stops a DM session with a user", usage="[user]", aliases=["close"])
    async def dm_stop_command(self, ctx, *, user: discord.Member):
        if user.dm_channel.id not in self.linked:
            return await ctx.send("❌ No DM session with user")
        
        session = self.linked.get(user.dm_channel.id)
        channel = self.bot.get_channel(session.channel)
        try:
            await channel.delete()
        except:
            pass

        self.linked.pop(user.dm_channel.id)
        self.linked.pop(channel.id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        session = self.linked.get(message.channel.id)

        if not session:
            return
        
        if isinstance(session, Session):
            if self.linked[session.channel].webhook.id == message.author.id:
                return

            msg = await session.webhook.send(f"{message.content}\n{', '.join([x.url for x in message.attachments])}", username=message.author.display_name, avatar_url=message.author.avatar_url, embeds=message.embeds, wait=True)
            session.messages[message.id] = msg.id
        
        if isinstance(session, DMSession):
            #Ignore the message if it's the bot
            #This way, the bot won't spam the same message over and over
            if message.author.id == self.bot.user.id:
                return

            destination = self.bot.get_channel(session.channel)

            msg = await destination.send(message.content)
            session.messages[message.id] = msg.id

    @commands.Cog.listener("on_message_delete")
    async def on_message_delete(self, message):
        session = self.linked.get(message.channel.id)

        if not session:
            return
        

        if isinstance(session, Session):
            if self.linked[session.channel].webhook.id == message.author.id:
                return

            destination = self.bot.get_channel(session.channel)
            
            #Get the deleted message's message in the linked channel and delete it
            to_delete = await destination.fetch_message(session.messages[message.id])

            await to_delete.delete()
        
        if isinstance(session, DMSession):
            #This ignores the bot editing a message
            if message.author.id == self.bot.user.id:
                return
            
            destination = self.bot.get_channel(session.channel)
            
            msg = await destination.fetch_message(session.messages[message.id])
            await msg.delete()

    @commands.Cog.listener("on_typing")
    async def on_typing(self, channel, user, when):
        if user.id == self.bot.user.id:
            return

        session = self.linked.get(channel.id)
        
        if not session:
            return
        
        if isinstance(session, Session):
            #Trigger typing because someone is typing in the linked channel
            await self.bot.get_channel(session.channel).trigger_typing()

        if isinstance(session, DMSession):
            #Triger typing because the owner is typing
            await self.bot.get_channel(session.channel).trigger_typing()

    @commands.Cog.listener("on_message_edit")
    async def on_message_edit(self, before, after):
        """Runs when a message is edited"""

        session = self.linked.get(before.channel.id)

        if not session:
            return
        
        if isinstance(session, Session):
            #Since webhooks can't edit messages, return if the message isn't on the bottom
            if before.channel.last_message_id != before.id:
                return False

            destination = self.bot.get_channel(session.channel)

            #Get the message to edit, which we delete
            #Then send the after message with "(edited)" on the end
            to_delete = await destination.fetch_message(session.messages[before.id])

            await to_delete.delete()
            
            #Resend the message and add it to the message dict
            msg = await session.webhook.send(f"{after.content}  ⁽ᵉᵈᶦᵗᵉᵈ⁾", username=before.author.display_name, avatar_url=before.author.avatar_url, wait=True)
            session.messages[before.id] = msg.id

        if isinstance(session, DMSession):
            destination = self.bot.get_channel(session.channel)

            #Get the message and edit it
            msg = await destination.fetch_message(session.messages[before.id])
            await msg.edit(content=after.content)

def setup(bot):
    bot.add_cog(Linker(bot))