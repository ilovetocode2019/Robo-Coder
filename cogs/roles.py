import asyncio
import re

import asyncpg
import discord
from discord.ext import commands

from .utils import cache

def get_reaction_roles_embed(title, color, reaction_roles):
    em = discord.Embed(title=title, description="Use the reactions on this message to assign yourself roles.\n", color=color)

    for role_id in reaction_roles:
        em.description += f"\n{reaction_roles[role_id]} | <@&{role_id}>"

    if not reaction_roles:
        em.description += "\nNo reaction roles added to this menu yet. Add some before posting."

    em.set_footer(text="If clicking a reaction doesn't affect your roles, try clicking it again and/or reload discord.")

    return em

class ViewAlreadyStopped(Exception):
    """An activity happened in the view callback, but the view was already stopped."""

    pass

class BaseReactionRoleView(discord.ui.View):
    def __init__(self, ctx, message, title, color, reaction_roles=None):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.message = message
        self.is_done = False

        self.is_active = asyncio.Event()
        asyncio.create_task(self.timeout_handler())

        self.title = title
        self.color = color
        self.reaction_roles = reaction_roles or {}

    @discord.ui.button(label="Title", style=discord.ButtonStyle.green, row=1)
    async def change_title(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()

        message = await self.message.reply("What would you like to change the title of the menu to?")
        self.messages.append(message)

        message = await self.wait_for_message()
        self.messages.append(message)

        self.title = message.content
        await self.cleanup_action()

    @discord.ui.button(label="Color", style=discord.ButtonStyle.green, row=1)
    async def change_color(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()

        message = await self.message.reply("What would you like to change the color of the menu to?")
        self.messages.append(message)

        while True:
            message = await self.wait_for_message()
            self.messages.append(message)

            try:
                color = await commands.ColorConverter().convert(self.ctx, message.content)
                break
            except commands.BadArgument:
                message = await message.reply(":x: That is not a valid color. Try again.")

            self.messages.append(message)

        self.color = color
        await self.cleanup_action()

    @discord.ui.button(label="Add", style=discord.ButtonStyle.green, row=1)
    async def add_reaction_role(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        if len(self.reaction_roles) > 20:
            return await interaction.response.send_message("Sorry. The limit for reaction roles in a single menu is 20! In order to have more reaction roles, you must use multiple reaction role menus.", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()

        message = await self.message.reply("Which role would you like to add to the reaction role menu?")
        self.messages.append(message)

        while True:
            message = await self.wait_for_message()
            self.messages.append(message)

            try:
                role = await commands.RoleConverter().convert(self.ctx, message.content)

                if role in self.reaction_roles:
                    message = await message.reply(":x: That role is already in this reaction role menu. Try again.")
                elif role.is_default() or role.managed:
                    message = await message.reply(":x: You cannot use this role as a reaction role. Try again.")
                elif role > self.ctx.author.top_role:
                    return await ctx.send(":x: This role is higher than your highest role")
                elif role > self.ctx.me.top_role:
                    return await ctx.send(":x: This role is higher than my highest role")

                else:
                    break
            except commands.BadArgument:
                message = await message.reply(":x: That is not a valid role. Try again.")

            self.messages.append(message)


        message = await message.reply("What emoji do you want to represent this role? This emoji be used as the reaction for this role.")
        self.messages.append(message)

        while True:
            message = await self.wait_for_message()
            self.messages.append(message)

            if message.content in self.ctx.bot.default_emojis or re.match(r"^(<a?)?:\w+:(\d{18}>)$", message.content):
                if message.content in self.reaction_roles.values():
                    message = await message.reply(":x: That emoji is already in use for this reaction role menu. Try again.")
                else:
                    emoji = message.content
                    break
            else:
                message = await message.reply(":x: That is not a valid emoji. Make sure the emoji is supported by discord or a custom emoji that belongs to this server and then try again.")

            self.messages.append(message)

        self.reaction_roles[role.id] = emoji
        await self.cleanup_action()

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red, row=1)
    async def remove_reaction_role(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        if not self.reaction_roles:
            return await interaction.response.send_message("No reaction roles to remove. Try adding some instead!", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()

        message = await self.message.reply("Which role would you like to remove from the reaction role menu?")
        self.messages.append(message)

        while True:
            message = await self.wait_for_message()
            self.messages.append(message)

            try:
                role = await commands.RoleConverter().convert(self.ctx, message.content)

                if role.id not in self.reaction_roles.keys():
                    message = await message.send(":x: This role is not in the reaction role menu. Try again.")
                else:
                    break
            except commands.BadArgument:
                message = await message.reply(":x: That is not a valid role. Try again.")

            self.messages.append(message)

        del self.reaction_roles[role.id]
        await self.cleanup_action()

    async def interaction_check(self, interaction):
        if interaction.user.id == self.ctx.author.id:
            return True
        else:
            await interaction.response.send_message("Sorry, you're not allowed to use these buttons.", empheral=True)

    async def on_error(self, interaction, error, item):
        if isinstance(error, asyncio.TimeoutError):
            await self.message.reply("Reaction role creation has timed out.")
        elif not isinstance(error, ViewAlreadyStopped):
            await super().on_error(interaction, error, item)
            await self.message.reply(f"An unexpected error has occured while using this menu: `{str(error)}`")

        await self.done()

    async def wait_for_message(self):
        message = await self.ctx.bot.wait_for("message", check=lambda message: message.channel == self.ctx.channel and message.author.id == self.ctx.author.id, timeout=180)

        if self.is_done:
            raise ViewAlreadyStopped()

        return message

    async def setup_action(self):
        self.is_active.set()
        self.messages = []

    async def timeout_handler(self):
        try:
            self.now = await asyncio.wait_for(self.is_active.wait(), timeout=180)
        except asyncio.TimeoutError:
            await self.message.reply("Reaction role creation has timed out.")
            await self.done()

class ReactionRoleView(BaseReactionRoleView):
    @discord.ui.button(label="Post", style=discord.ButtonStyle.blurple, row=2)
    async def post(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        if not self.reaction_roles:
            return await interaction.response.send_message("It looks like you don't have any reaction roles added to the menu yet. Try adding some first!", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()
        await self.message.reply("Where should the reaction role menu be sent to?")


        while True:
            message = await self.wait_for_message()

            try:
                channel = await commands.TextChannelConverter().convert(self.ctx, message.content)
                permissions = channel.permissions_for(self.ctx.me)

                if not permissions.send_messages:
                    await self.ctx.send(":x: I don't have permission to send messages in this channel. Choose a different channel or fix the permissions, and then try again.")
                elif not permissions.add_reactions:
                    await self.ctx.send(":x: I don't have permission to add reactions in this channel. Choose a diferent channel or fix the permissions, and then try again.")
                else:
                    break
            except commands.BadArgument:
                await self.ctx.send(":x: That is not a valid channel. Try again.")

        await self.ctx.typing()
        post = await channel.send(embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles))

        for role_id in self.reaction_roles:
            await post.add_reaction(self.reaction_roles[role_id])

        query = """INSERT INTO reaction_roles(guild_id, channel_id, message_id, title, color, roles)
                   VALUES($1, $2, $3, $4, $5, $6);
                """
        await self.ctx.bot.db.execute(query, channel.guild.id, channel.id, post.id, self.title, int(self.color), [(role_id, color) for role_id, color in self.reaction_roles.items()])

        await message.reply(f"Posted reaction role menu to {channel.mention} successfully. Deleting the message will delete and disable the reaction role menu.")
        await self.done()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=2)
    async def cancel(self, interaction, button):
        await interaction.response.send_message("Canceled reaction role creation.")
        await self.done()

    async def cleanup_action(self):
        if self.ctx.bot_permissions.manage_messages:
            await self.message.edit(content="Here is what your reaction role menu will look like when it is sent. Use the buttons on this message to edit and complete the menu.", embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles), view=self)
            self.is_active.clear()
            await self.ctx.channel.delete_messages(self.messages)
            asyncio.create_task(self.timeout_handler())
        else:
            await self.message.delete()

            message = await self.ctx.reply(content="Here is what your reaction role menu will look like when it is sent. Use the buttons on this message to edit and complete the menu.", embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles))
            await message.edit(view=ReactionRoleView(self.ctx, message, self.title, self.color, self.reaction_roles))

            self.is_active.clear()
            self.stop()

    async def done(self):
        self.add_reaction_role.disabled = True
        self.remove_reaction_role.disabled = True
        self.change_title.disabled = True
        self.change_color.disabled = True
        self.post.disabled = True
        self.cancel.disabled = True

        await self.message.edit(content="The buttons on this message are no longer active.", view=self)
        self.is_done = True
        self.stop()

class ReactionRoleEditView(BaseReactionRoleView):
    def __init__(self, ctx, message, title, color, reaction_roles, location):
        super().__init__(ctx, message, title, color, reaction_roles)
        self.color = color
        self.location = location

    @discord.ui.button(label="Save", style=discord.ButtonStyle.blurple, row=2)
    async def save(self, interaction, button):
        if self.is_active.is_set():
            return await interaction.response.send_message("Complete the current action first!", ephemeral=True)

        await self.setup_action()
        await interaction.response.defer()
        await self.ctx.typing()

        if self.ctx.bot_permissions.manage_messages:
            await self.location.clear_reactions()

        await self.location.edit(embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles))

        for reaction in list(self.reaction_roles.values()):
            await self.location.add_reaction(reaction)

        query = """UPDATE reaction_roles
                   SET title=$1, color=$2, roles=$3::jsonb
                   WHERE reaction_roles.guild_id=$4 AND reaction_roles.channel_id=$5 AND reaction_roles.message_id=$6;
                """
        await self.ctx.bot.db.execute(query, self.title, int(self.color), [(role, color) for role, color in self.reaction_roles.items()], self.location.channel.guild.id, self.location.channel.id, self.location.id)
        self.ctx.cog.get_reaction_roles.invalidate(self, (self.location.channel.guild.id, self.location.channel.id, self.location.id))

        await self.message.reply("Reaction role menu was updated successfully.")
        await self.done()

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.gray, row=2)
    async def discard(self, interaction, button):
        await interaction.response.send_message("All changes have been discarded.")
        await self.done()

    async def cleanup_action(self):
        if self.ctx.bot_permissions.manage_messages:
            await self.message.edit(content="Here is what your reaction role menu will look like when it is updated. Use the buttons on this message to edit and complete the menu.", embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles), view=self)
            self.is_active.clear()
            await self.ctx.channel.delete_messages(self.messages)
            asyncio.create_task(self.timeout_handler())
        else:
            await self.message.delete()

            message = await self.ctx.reply(content="Here is what your reaction role menu will look like when it is updated. Use the buttons on this message to edit and complete the menu.", embed=get_reaction_roles_embed(self.title, self.color, self.reaction_roles))
            await message.edit(view=ReactionRoleEditView(self.ctx, message, self.title, self.color, self.reaction_roles, self.location))

            self.is_active.clear()
            self.stop()

    async def done(self):
        self.add_reaction_role.disabled = True
        self.remove_reaction_role.disabled = True
        self.change_title.disabled = True
        self.change_color.disabled = True
        self.save.disabled = True
        self.discard.disabled = True

        await self.message.edit(content="The buttons on this message are no longer active.", view=self)
        self.is_done = True
        self.stop()

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji  = ":label:"

    @commands.group(name="reactionrole", description="Allow server members to assign specified roles to themselves through reactions", aliases=["reactionroles"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def reactionrole(self, ctx):
        await ctx.send_help(ctx.command)

    @reactionrole.command(name="create", description="Set up a reaction role menu for server members to assign themselves roles.")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def reactionrole_create(self, ctx):
        await ctx.reply("What should this reaction role menu be called. This will be show as the title of the posted menu.")

        try:
            message = await self.bot.wait_for("message", check=lambda message: message.channel == ctx.channel and message.author.id == ctx.author.id, timeout=180)
        except asyncio.TimeoutError:
            return await ctx.send("Reaction role creation has timed out.")

        title = message.content

        message = await ctx.send("Here is what your reaction role menu will look like when it is sent. Use the buttons on this message to edit and complete the menu.")
        view = ReactionRoleView(ctx, message, title, 0x96c8da)
        await message.edit(embed=get_reaction_roles_embed(title, 0x96c8da, {}), view=view)

    @reactionrole.command(name="edit", description="Make modifications to an already existing reaction role menu.")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def reactionrole_edit(self, ctx, message: discord.Message):
        reaction_roles = await self.get_reaction_roles((message.guild.id, message.channel.id, message.id))
        title, color, reaction_roles = reaction_roles[0], reaction_roles[1], {value.id: key for key, value in reaction_roles[2].items()}

        if not reaction_roles:
            return await ctx.send(":x: This message is not a reaction role menu.")

        if message.channel.permissions_for(ctx.me).send_messages == False:
            return await ctx.send(":x: It appears you don't have permission to send messages in this channel. Ask someone to give you permission, or try a different channel.")
        if message.channel.permissions_for(ctx.me).add_reactions == False:
            return await ctx.send(":x: It appears you don't have permission to add reactions in this channel. Ask someone to give you permission, or try a different channel.")

        if message.channel.permissions_for(ctx.me).send_messages == False:
            return await ctx.send(":x: It appears I no longer have permission to send messages in the channel where the menu is. You need to enable them for me before I can edit them.")
        if message.channel.permissions_for(ctx.me).add_reactions == False:
            return await ctx.send(":x: It appears I no longer have permission to send messages in the channel where the menu is. You need to enable them for me before I can edit them.")

        location = message

        message = await ctx.send("Here is what your reaction role menu will look like when it is updated. Use the buttons on this message to edit and complete the menu.")
        view = ReactionRoleEditView(ctx, message, title, color, reaction_roles, location)
        await message.edit(embed=get_reaction_roles_embed(title, color, reaction_roles), view=view)

    @reactionrole.command(name="sync", description="Sync the reaction role menu to fix any issues (e.g. role was deleted or reactions were removed)")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def reactionrole_sync(self, ctx, message: discord.Message):
        await ctx.typing()

        reaction_roles = await self.get_reaction_roles((message.guild.id, message.channel.id, message.id))
        title, color, reaction_roles = reaction_roles[0], reaction_roles[1], {value.id: key for key, value in reaction_roles[2].items()}

        if not reaction_roles:
            return await ctx.send(":x: This message is not a reaction role menu.")

        if message.channel.permissions_for(ctx.me).send_messages == False:
            return await ctx.send(":x: It appears you don't have permission to send messages in this channel. Ask someone to give you permission, or try a different channel.")
        if message.channel.permissions_for(ctx.me).add_reactions == False:
            return await ctx.send(":x: It appears you don't have permission to add reactions in this channel. Ask someone to give you permission, or try a different channel.")

        if message.channel.permissions_for(ctx.me).send_messages == False:
            return await ctx.send(":x: It appears I no longer have permission to send messages in the channel where the menu is. You need to enable them for me before I can edit them.")
        if message.channel.permissions_for(ctx.me).add_reactions == False:
            return await ctx.send(":x: It appears I no longer have permission to send messages in the channel where the menu is. You need to enable them for me before I can edit them.")

        if ctx.bot_permissions.manage_messages:
            await self.location.clear_reactions()

        await message.edit(embed=get_reaction_roles_embed(title, color, reaction_roles))

        for reaction in list(reaction_roles.values()):
            await message.add_reaction(reaction)

        query = """UPDATE reaction_roles
                   SET roles=$1::jsonb
                   WHERE reaction_roles.guild_id=$2 AND reaction_roles.channel_id=$3 AND reaction_roles.message_id=$4;
                """
        await self.bot.db.execute(query, [(role, color) for role, color in reaction_roles.items()], message.channel.guild.id, message.channel.id, message.id)
        self.get_reaction_roles.invalidate(self, (message.channel.guild.id, message.channel.id, message.id))

        await ctx.send("Reaction role menu was synced, and any issues should be fixed.")

    @commands.group(name="autorole", description="Automaticly assign roles to users with they join", aliases=["autoroles"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole(self, ctx):
        await ctx.send_help(ctx.command)

    @autorole.command(name="list", description="Show the autorole list")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_list(self, ctx):
        autoroles = await self.get_autoroles(ctx.guild.id)

        if not autoroles:
            return await ctx.send("No autoroles registered")

        roles = [f"{counter+1}. {str(role.mention)}" for counter, role in enumerate(autoroles)]
        roles = "\n".join(roles)

        await ctx.send(roles, allowed_mentions=discord.AllowedMentions.none())

    @autorole.command(name="add", description="Add a role to the autorole list")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_add(self, ctx, *, role: discord.Role):
        if role.is_default() or role.managed:
            return await ctx.send(":x: You can't use this role as an autorole")
        elif role > ctx.author.top_role:
            return await ctx.send(":x: This role is higher than your highest role")
        elif role > ctx.me.top_role:
            return await ctx.send(":x: This role is higher than my highest role")

        autoroles = await self.get_autoroles(ctx.guild.id)
        if len(autoroles) >= 5:
            return await ctx.send(":x: You are not allowed to have more than 5 autoroles")

        if role in autoroles:
            return await ctx.send(":x: This role is already set as an autorole")

        query = """INSERT INTO autoroles (guild_id, role_id)
                   VALUES ($1, $2)
                """
        await self.bot.db.execute(query, ctx.guild.id, role.id)

        self.get_autoroles.invalidate(self, ctx.guild.id)

        await ctx.send(":white_check_mark: Added role to autorole list")

    @autorole.command(name="remove", description="Remove a role from the autorole list")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx, *, role: discord.Role):
        query = """DELETE FROM autoroles
                   WHERE autoroles.role_id=$1
                """
        result = await self.bot.db.execute(query, role.id)

        if result == "DELETE 0":
            return await ctx.send(":x: This role is not set as an autorole")

        self.get_autoroles.invalidate(self, role.guild.id)

        await ctx.send(":white_check_mark: Removed role from autorole list")

    @cache.cache()
    async def get_autoroles(self, guild_id):
        query = """SELECT *
                   FROM autoroles
                   WHERE autoroles.guild_id=$1;
                """
        autoroles = await self.bot.db.fetch(query, guild_id)

        guild = self.bot.get_guild(guild_id)
        roles = [guild.get_role(auto_role["role_id"]) for auto_role in autoroles]
        return [role for role in roles if role]

    @cache.cache()
    async def get_reaction_roles(self, message):
        guild_id, channel_id, message_id = message

        query = """SELECT *
                   FROM reaction_roles
                   WHERE reaction_roles.guild_id=$1 AND reaction_roles.channel_id=$2 AND reaction_roles.message_id=$3;
                """
        reaction_roles = await self.bot.db.fetchrow(query, guild_id, channel_id, message_id)

        if not reaction_roles:
            return None

        guild = self.bot.get_guild(guild_id)
        return (
            reaction_roles["title"],
            discord.Color(int(reaction_roles["color"])),
            {reaction_role[1]: guild.get_role(reaction_role[0]) for reaction_role in reaction_roles["roles"]}
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if member.bot:
            return

        message = (payload.guild_id, payload.channel_id, payload.message_id)
        reaction_roles = await self.get_reaction_roles(message)

        if reaction_roles:
            if payload.emoji.id:
                emoji = f"<:{payload.emoji.name}:{payload.emoji.id}>"
            else:
                emoji = payload.emoji.name

            role = reaction_roles[2].get(emoji)
            if role:
                await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if member.bot:
            return

        message = (payload.guild_id, payload.channel_id, payload.message_id)
        reaction_roles = await self.get_reaction_roles(message)

        if reaction_roles:
            if payload.emoji.id:
                emoji = f"<:{payload.emoji.name}:{payload.emoji.id}>"
            else:
                emoji = payload.emoji.name

            role = reaction_roles[2].get(emoji)
            if role:
                await member.remove_roles(role)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        query = """DELETE FROM reaction_roles
                   WHERE reaction_roles.channel_id=$1;
                """
        await self.bot.db.execute(query, channel.id)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        query = """DELETE FROM reaction_roles
                   WHERE reaction_roles.channel_id=$1 AND reaction_roles.message_id=$2;
                """
        await self.bot.db.execute(query, payload.channel_id, payload.message_id)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if await self.get_autoroles(role.guild.id):
            query = """DELETE FROM autoroles
                       WHERE autoroles.role_id=$1;
                    """
            await self.bot.db.execute(query, role.id)
            self.get_autoroles.invalidate(self, role.guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        roles = await self.get_autoroles(member.guild.id)
        await member.add_roles(*(role for role in roles if role))

async def setup(bot):
    await bot.add_cog(Roles(bot))
