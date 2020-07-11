from discord.ext import commands
import discord

class Session:
    """Represents a session with another channel"""

    def __init__(self, channel, webhook):
        self.channel = channel
        self.webhook = webhook
        self.messages = {}

class Linker(commands.Cog):
    """Linking two channels together"""

    def __init__(self, bot):
        self.bot = bot
        self.linked = {}
    
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

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        session = self.linked.get(message.channel.id)

        if not session or self.linked[session.channel].webhook.id == message.author.id:
            return
        
        msg = await session.webhook.send(message.content, username=message.author.display_name, avatar_url=message.author.avatar_url, embeds=message.embeds,wait=True)
        session.messages[message.id] = msg.id

    @commands.Cog.listener("on_message_delete")
    async def on_message_delete(self, message):

        session = self.linked.get(message.channel.id)

        if not session or self.linked[session.channel].webhook.id == message.author.id:
            return

        destination = self.bot.get_channel(session.channel)
        
        #Get the deleted message's message in the linked channel and delete it
        to_delete = await destination.fetch_message(session.messages[message.id])

        await to_delete.delete()

    @commands.Cog.listener("on_typing")
    async def on_typing(self, channel, user, when):
        if user.id == self.bot.user.id:
            return

        session = self.linked.get(channel.id)
        
        if not session:
            return
        
        #Trigger typing because someone is typing in the linked channel
        await self.bot.get_channel(session.channel).trigger_typing()

    @commands.Cog.listener("on_message_edit")
    async def on_message_edit(self, before, after):
        """Runs when a message is edited"""

        session = self.linked.get(before.channel.id)

        if not session:
            return
        
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

def setup(bot):
    bot.add_cog(Linker(bot))