import asyncio
import logging
import time
from random import choice

import discord
from discord.ext import commands
from sqlitedict import SqliteDict

from classes import DeleteProcess, PrivateRoom
from constants import (
    DECISION_REACTS,
    NO_REACT,
    PRIVY_DB,
    TEXT_COLOR,
    TIPS_DIRECTORY,
    YES_REACT,
)
from logger import logger


class MainCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.room_table = SqliteDict(PRIVY_DB, tablename="rooms")
        self.preference_table = SqliteDict(PRIVY_DB, tablename="preferences")
        self.delete_process_table = SqliteDict(
            PRIVY_DB, tablename="delete_process_queue"
        )

        tips = list()
        with open(TIPS_DIRECTORY) as f:
            for line in f:
                if line.endswith("\n"):
                    line = line[:-1]
                tips.append(line)

        self.tips = tips

    # -- HELPER FUNCTIONS -- #

    async def get_room_channel(self, room: PrivateRoom, type: str):
        ret = None
        if type == "voice":
            ret = self.bot.get_guild(room.guild_id).get_channel(
                room.private_voice_id
            )
        elif type == "text":
            ret = self.bot.get_guild(room.guild_id).get_channel(
                room.private_text_id
            )
        elif type == "waiting":
            ret = self.bot.get_guild(room.guild_id).get_channel(
                room.waiting_room_id
            )

        return ret

    def get_waiting_room_id_dict(self):
        return {
            int(room.waiting_room_id): room
            for room in self.room_table.values()
        }

    def get_private_voice_id_dict(self):
        return {
            int(room.private_voice_id): room
            for room in self.room_table.values()
        }

    def get_owner_ids(self):
        return [int(key) for key in self.room_table.keys()]

    # -- ROOM HELPER FUNCTIONS -- #

    async def delete_room(self, room: PrivateRoom):
        voice = await self.get_room_channel(room, "voice")
        text = await self.get_room_channel(room, "text")
        waiting = await self.get_room_channel(room, "waiting")
        await voice.delete()
        await text.delete()
        await waiting.delete()

        logger.debug(f"Closed {room.owner_id}'s room")

        self.room_table.pop(room.owner_id)
        self.room_table.commit()

    async def create_room(self, member: discord.Member):
        # TODO: Docstring

        # Checks for existing room
        # if yes, kicks them out of the channel and stops the function
        if member.id in self.room_table.keys():
            for room in self.room_table.values():
                if room.owner == member:
                    await member.send(
                        content=f"You already have a private room "
                        f"in {room.owner.private_voice.guild}! "
                        f"Close it to make a new one."
                    )
                    await member.move_to(None)
                    return None

        # TODO: make a function get_category_from_id
        # Searches for category object from category_id
        category_id = self.preference_table.get(member.guild.id).get(
            "lobby_category"
        )
        category = None
        for cat in member.guild.categories:
            if cat.id == category_id:
                category = cat
                break

        if category:
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    connect=False
                ),
                member: discord.PermissionOverwrite(connect=True),
                member.guild.me: discord.PermissionOverwrite(connect=True),
            }

            # Creates a Private Room object and channels
            new_room = PrivateRoom()

            new_room.guild_id = member.guild.id
            new_room.owner_id = member.id
            new_room.private_voice_id = (
                await member.guild.create_voice_channel(
                    f"{member.name}'s Room",
                    category=category,
                    overwrites=overwrites,
                )
            ).id

            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                member: discord.PermissionOverwrite(read_messages=True),
                member.guild.me: discord.PermissionOverwrite(
                    read_messages=True
                ),
            }

            new_room.private_text_id = (
                await member.guild.create_text_channel(
                    f"{member.name}s-chat",
                    category=category,
                    overwrites=overwrites,
                )
            ).id
            new_room.waiting_room_id = (
                await member.guild.create_voice_channel(
                    f"{member.name}'s Waiting Room", category=category
                )
            ).id

            self.room_table[new_room.owner_id] = new_room
            self.room_table.commit()

            logger.debug(
                f"""Private voice: {
                    await self.get_room_channel(new_room, "voice")
                    }"""
            )
            await member.move_to(
                await self.get_room_channel(new_room, "voice")
            )

            embed = discord.Embed(
                title="Welcome to your Private Room!",
                description="To see the list of commands, use pr!help."
                "Please be reminded that server administrators "
                "can still access your private channels!",
                color=TEXT_COLOR,
            )
            embed.add_field(name="Tip", value=choice(self.tips))
            embed.set_footer(
                text="Made by Anthemic | Icon by Creartive",
                icon_url="https://i.imgur.com/JBNXE4g.png",
            )

            text = await self.get_room_channel(new_room, "text")
            await text.send(embed=embed)
            logger.debug(f"Created a room for {member}")

    async def check_lobby(
        self, member: discord.Member, after: discord.VoiceState
    ):
        """
        Checks if member joins the lobby channel
        and does not have a room.
        """

        if (
            after.channel.id
            == self.preference_table.get(member.guild.id).get("lobby_channel")
            and member.id not in self.get_owner_ids()
        ):
            logger.debug(f"{member} joined lobby channel: {after.channel}")
            await self.create_room(member)

        elif (
            after.channel.id
            == self.preference_table.get(member.guild.id).get("lobby_channel")
            and member.id in self.get_owner_ids()
        ):
            await member.send(
                content="You already have a private room in some server! "
                "Close it to make a new one."
            )
            await member.move_to(None)

    async def check_waiting_room(
        self, member: discord.Member, after: discord.VoiceState
    ):
        """
        Messages the private text channel when someone joins the
        appropriate waiting room.
        """
        w_room_dict = self.get_waiting_room_id_dict()

        if after.channel.id in w_room_dict.keys():
            logger.debug(
                f"{member} joined waiting room channel: {after.channel}"
            )
            room = w_room_dict[after.channel.id]
            private_voice = await self.get_room_channel(room, "voice")
            private_text = await self.get_room_channel(room, "text")

            embed = discord.Embed(
                title="Requesting access",
                description=f"<@{room.owner_id}> {member} has joined "
                f"your waiting room. React {YES_REACT} to grant access "
                f"or {NO_REACT} to kick them.",
                color=TEXT_COLOR,
            )
            confirm_message = await private_text.send(embed=embed)

            await confirm_message.add_reaction(YES_REACT)
            await confirm_message.add_reaction(NO_REACT)

            def check(r, u):
                return (
                    u.id == int(room.owner_id)
                    and str(r.emoji) in DECISION_REACTS
                    and r.message == confirm_message
                )

            reaction, user = await self.bot.wait_for(
                "reaction_add", check=check
            )

            if str(reaction.emoji) == YES_REACT:

                await private_text.send(
                    content=f"Let {member} into your private room.",
                    delete_after=5,
                )
                await member.move_to(private_voice)

                overwrite = discord.PermissionOverwrite()
                overwrite.connect = True
                await private_voice.set_permissions(
                    member, overwrite=overwrite
                )

                overwrite = discord.PermissionOverwrite()
                overwrite.read_messages = True
                overwrite.send_messages = True
                await private_text.set_permissions(member, overwrite=overwrite)

            elif str(reaction.emoji) == NO_REACT:
                waiting_room = await self.get_room_channel(room, "waiting")
                if member in waiting_room.members:
                    embed = discord.Embed(
                        title="Denied access",
                        description=f"Kicked {member} from your waiting room.",
                        color=TEXT_COLOR,
                    )
                    await private_text.send(embed=embed, delete_after=5)
                    await member.move_to(None)
                else:
                    embed = discord.Embed(
                        title="Denied access",
                        description=f"{member} is not in your waiting room!",
                        color=TEXT_COLOR,
                    )
                    await private_text.send(embed=embed, delete_after=5)

            await confirm_message.delete()

    async def check_empty_room(
        self, member: discord.Member, before: discord.VoiceState
    ):
        """
        Called on every voice state update, this deletes a channel after
        5 minutes.
        """
        private_voice_dict = self.get_private_voice_id_dict()

        if before.channel.id in private_voice_dict.keys():
            if before.channel.members:
                pass
            else:
                room = private_voice_dict[before.channel.id]
                await self.check_return(room)

    async def check_empty_rooms_on_ready(self):
        private_voice_dict = self.get_private_voice_id_dict()

        for room in private_voice_dict.values():
            private_voice = await self.get_room_channel(room, "voice")
            if not private_voice.members:
                await self.check_return(room)

    async def check_return(self, room):
        def check(_, __, after_):
            return after_.channel.id == room.private_voice_id

        private_text = await self.get_room_channel(room, "text")
        embed = discord.Embed(
            title="Private Room closing in 5 minutes",
            description="To prevent it from closing, rejoin the private voice "
            "channel. Use pr!close to immediately close it.",
            color=TEXT_COLOR,
        )
        warning_message = await private_text.send(
            embed=embed, delete_after=300
        )
        try:
            await self.bot.wait_for(
                "voice_state_update", check=check, timeout=300
            )

            embed = discord.Embed(
                title="Private Room no longer closing",
                description="A user has rejoined the private voice channel.",
                color=TEXT_COLOR,
            )
            await private_text.send(embed=embed, delete_after=5)

            await warning_message.delete()
        except asyncio.TimeoutError:
            await self.delete_room(room)

    # -- EVENT LISTENERS -- #

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Initializes databases and updates bot presence upon connecting to the
        Discord API.
        """

        logger.info(f"Successfully logged in as {self.bot.user}")

        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="pr!help"
            )
        )
        await self.check_empty_rooms_on_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        try:
            await self.check_lobby(member, after)
        except AttributeError:
            pass

        try:
            await self.check_waiting_room(member, after)
        except AttributeError:
            pass

        try:
            await self.check_empty_room(member, before)
        except AttributeError:
            pass

    # -- USER COMMANDS -- #

    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx: commands.Context):
        """
        Displays the help menu containing user commands and
        their descriptions.
        """

        embed = discord.Embed(
            title="Privy's User Commands",
            description="I'm a Discord bot that adds privacy functions "
            "to your server, "
            "like private rooms and bulk deleting!",
            color=TEXT_COLOR,
        )
        embed.add_field(
            name="pr!help | pr!h", value="Shows this menu", inline=True
        )
        embed.add_field(
            name="pr!close | pr!c",
            value="Closes your private room",
            inline=True,
        )
        embed.add_field(
            name="pr!lobby | pr!l",
            value="Tells you what the lobby channel of the server is",
            inline=True,
        )
        embed.add_field(
            name="pr!changename <name> | pr!cn",
            value="Changes the name of your room. Useable once per 5 minutes",
            inline=True,
        )
        embed.add_field(
            name="pr!kick <ID> | pr!k",
            value="Revokes access and kicks a user from your room. Ex. pr!k "
            "Anthemic#6661",
            inline=True,
        )
        embed.add_field(
            name="pr!invite <ID> <msg> | pr!inv",
            value="Grants access to a user. If a message is included, the bot "
            "will send a DM to the user containing it. "
            "Ex. pr!inv Anthemic#6661 Come chill!",
            inline=False,
        )
        embed.add_field(
            name="pr!ahelp | pr!ah",
            value="Shows the admin commands",
            inline=False,
        )
        embed.set_footer(
            text="Made by Anthemic | Icon by Creartive",
            icon_url="https://i.imgur.com/JBNXE4g.png",
        )
        await ctx.send(embed=embed)

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Returns ping."""
        start_time = time.time()
        message = await ctx.send("Testing Ping...")
        end_time = time.time()

        await message.edit(
            content=f"""Pong! {round(self.bot.latency * 1000)}ms
            API: {round((end_time - start_time) * 1000)}ms"""
        )

    @commands.command(name="close", aliases=["c"])
    async def close_room(self, ctx: commands.Context):
        try:
            await self.delete_room(self.room_table[ctx.author.id])
        except AttributeError:
            await ctx.send("You must own a room to use this!", delete_after=5)
        except KeyError:
            await ctx.send("You must own a room to use this!", delete_after=5)

    @commands.command(name="kick", aliases=["k"])
    async def kick(self, ctx: commands.Context, target_handle):
        target_member = ctx.guild.get_member_named(target_handle)

        if target_member is None:
            await ctx.send(content="Could not find that user!", delete_after=5)
            return None

        try:
            room = self.room_table[str(ctx.author.id)]
            private_voice = await self.get_room_channel(room, "voice")
            private_text = await self.get_room_channel(room, "text")

            if target_member in private_voice.members:
                await target_member.move_to(None)

            overwrite = discord.PermissionOverwrite()
            overwrite.connect = False
            await private_voice.set_permissions(
                target_member, overwrite=overwrite
            )

            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = False
            overwrite.send_messages = False
            await private_text.set_permissions(
                target_member, overwrite=overwrite
            )

            embed = discord.Embed(
                title=f"Kicked {target_handle} successfully",
                description=f"Revoked access from {target_handle} for your "
                "private room.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
        except AttributeError:
            embed = discord.Embed(
                title="Kicking failed",
                description="You must own a room to do this.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
            pass

    @commands.command(name="invite", aliases=["inv"])
    async def invite(self, ctx: commands.Context, target_handle, *args):
        target_member = ctx.guild.get_member_named(target_handle)

        if target_member is None:
            embed = discord.Embed(
                title="Invite failed",
                description="Could not find that user.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
            return None

        try:
            room = self.room_table[ctx.author.id]
            private_voice = await self.get_room_channel(room, "voice")
            private_text = await self.get_room_channel(room, "text")

            overwrite = discord.PermissionOverwrite()
            overwrite.connect = True
            await private_voice.set_permissions(
                target_member, overwrite=overwrite
            )

            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = True
            overwrite.send_messages = True
            await private_text.set_permissions(
                target_member, overwrite=overwrite
            )

            if args:
                message = ""
                for arg in args:
                    message += arg + " "

                embed = discord.Embed(
                    title="Invite sent",
                    description=f"Granted access to {target_handle} into your "
                    "private room and sent the user a DM.\n"
                    f"{ctx.author.name}#{ctx.author.discriminator}'s "
                    f"Message: {message}",
                    color=TEXT_COLOR,
                )
                await ctx.send(embed=embed, delete_after=5)

                embed = discord.Embed(
                    title="Invitation",
                    description=f"You have been invited into "
                    f"{ctx.message.author}'s Private Room in "
                    f"{ctx.guild}. \nMessage: {message}",
                    color=TEXT_COLOR,
                )
                await target_member.send(embed=embed)

            else:
                embed = discord.Embed(
                    title="Invite sent",
                    description=f"Granted access to {target_handle} "
                    "into your private room.",
                    color=TEXT_COLOR,
                )
                await ctx.send(embed=embed, delete_after=5)

        except AttributeError:
            embed = discord.Embed(
                title="Invite failed",
                description="You must own a room to do this.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
            pass

    @commands.command(name="lobby", aliases=["l"])
    async def show_lobby(self, ctx: commands.Context):
        flag = 0

        for guild_id, prefs in self.preference_table.items():
            if guild_id == ctx.guild.id:
                lobby_channel_id = prefs.get("lobby_channel")
                for channel in ctx.guild.channels:
                    if lobby_channel_id == channel.id:
                        embed = discord.Embed(
                            title="Lobby channel",
                            description="The lobby channel for this server "
                            f"is {channel.name}.",
                            color=TEXT_COLOR,
                        )
                        await ctx.send(embed=embed, delete_after=5)
                        flag = 1
                        break
                break

        if not flag:
            embed = discord.Embed(
                title="Lobby channel",
                description="There is no lobby channel for this server.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)

    @commands.command(name="changename", aliases=["cn"])
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.member)
    async def change_name(self, ctx: commands.Context, *, name):
        try:
            room = self.room_table[ctx.author.id]
            private_voice = await self.get_room_channel(room, "voice")
            private_text = await self.get_room_channel(room, "text")
            waiting_room = await self.get_room_channel(room, "waiting")

            await private_text.edit(name=f"{name}-chat")
            await private_voice.edit(name=name)
            await waiting_room.edit(name=f"{name}'s Waiting Room")
            embed = discord.Embed(
                title="Name change successful",
                description=f"This Private Room is now named {name}",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
        except AttributeError:
            embed = discord.Embed(
                title="Name change failed",
                description="You must own a room to do this.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)

    # -- ADMIN COMMANDS -- #

    @commands.command(name="ahelp", aliases=["ah"])
    async def ahelp(self, ctx: commands.Context):
        """
        Displays the admin help menu containing admin commands
        and their descriptions.
        """

        embed = discord.Embed(
            title="Privy's Admin Commands",
            description="You must have the permission Manage Channels to "
            "run room-related commands and Manage Messages to run delete "
            "commands. Warning: Deleting room channels manually may "
            "interfere with my processes!",
            color=TEXT_COLOR,
        )
        embed.add_field(
            name="pr!setlobby | pr!sl",
            value="Sets the lobby channel to the voice channel you are "
            "currently in. You can only have one lobby per server",
            inline=False,
        )
        embed.add_field(
            name="pr!deletelobby | pr!dl",
            value="Deletes the lobby",
            inline=True,
        )
        embed.add_field(
            name="pr!listrooms | pr!lr",
            value="Lists all the server's rooms and their owners",
            inline=True,
        )
        embed.add_field(
            name="pr!forceclose <owner> | pr!fc",
            value="Closes any room in the server instantly. "
            "Ex. pr!fc Anthemic#6661",
            inline=True,
        )
        embed.add_field(
            name="pr!bulkdelete | pr!bdel",
            value="Starts a process to delete messages in bulk. Only works "
            "for the last 250 messages",
            inline=False,
        )
        embed.add_field(
            name="pr!deletelast <num> | pr!del",
            value="Deletes the last x number of messages. Ex. pr!del 100",
            inline=True,
        )
        embed.set_footer(
            text="Made by Anthemic | Icon by Creartive",
            icon_url="https://i.imgur.com/JBNXE4g.png",
        )
        await ctx.send(embed=embed)

    @commands.command(name="forceclose", aliases=["fc"])
    @commands.has_permissions(manage_channels=True)
    async def force_close(self, ctx: commands.Context, owner_handle):
        owner_member = ctx.guild.get_member_named(owner_handle)

        if owner_member is None:
            embed = discord.Embed(
                title="Force close failed",
                description="Could not find that user!",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
            return None

        try:
            room = self.room_table[owner_member.id]
            if room.guild_id == ctx.guild.id:
                await self.delete_room(room)
                logging.debug(
                    f"{ctx.author.id} force-closed {owner_handle}'s room"
                )

        except AttributeError:
            embed = discord.Embed(
                title="Force close failed",
                description=f"{owner_handle} does not own a room!",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)

    @commands.command(name="listrooms", aliases=["lr"])
    @commands.has_permissions(manage_channels=True)
    async def list_rooms(self, ctx: commands.Context):
        rooms_in_guild = {
            room.owner_id: room
            for room in self.room_table.values()
            if room.guild_id == ctx.guild.id
        }

        embed = discord.Embed(
            title=f"List of rooms in {ctx.guild}", color=TEXT_COLOR
        )

        if rooms_in_guild:
            for owner_id, room in rooms_in_guild.items():
                private_voice = await self.get_room_channel(room, "voice")
                owner_member = ctx.guild.get_member(room.owner_id)
                embed.add_field(
                    name=f"{private_voice.name}",
                    value=f"Owned by {owner_member.name}"
                    f"#{owner_member.discriminator}",
                    inline=True,
                )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"List of rooms in {ctx.guild}",
                description="There are no rooms in this server.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)

    @commands.command(name="deletelast", aliases=["del"])
    @commands.has_permissions(manage_messages=True)
    async def deleteLast(self, ctx: commands.Context, limit):
        msgs = await ctx.message.channel.history(limit=int(limit)).flatten()
        async with ctx.message.channel.typing():
            for msg in msgs:
                await msg.delete()
                await asyncio.sleep(0.5)
            embed = discord.Embed(
                title="Deletion successful",
                description=f"Deleted {len(msgs)} messages.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)

    @commands.command(name="bulkdelete", aliases=["bdel"])
    @commands.has_permissions(manage_messages=True)
    async def bulk_delete(self, ctx: commands.Context):
        new_process = DeleteProcess()
        new_process.doer_id = ctx.message.author.id
        self.delete_process_table[new_process.doer_id] = new_process
        self.delete_process_table.commit()

        embed = discord.Embed(
            title="Bulk deletion process",
            description="To bulk delete a range of messages, please react "
            "▶️ (arrow_forward) where you want me to start and react "
            "⏹️ (stop_button) where you want me to stop. To confirm or "
            f"cancel the deletion, react {YES_REACT} or {NO_REACT} "
            "respectively on this message. This process will time out "
            "after 2 minutes.",
        )
        embed.set_footer(
            text=f"Started by {ctx.message.author.name}\
                #{ctx.message.author.discriminator}"
        )
        instruct = await ctx.send(embed=embed)
        await instruct.add_reaction(YES_REACT)
        await instruct.add_reaction()
        await self.perform_delete_process(ctx, instruct, new_process.doer_id)

    async def perform_delete_process(
        self, ctx: commands.Context, instruct, doer_id
    ):

        check = (
            lambda r, u: u == ctx.message.author
            and str(r.emoji) in DECISION_REACTS
            and r.message == instruct
        )

        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add", check=check, timeout=120
            )

            process = self.delete_process_table[doer_id]
            if str(reaction.emoji) == YES_REACT:
                async with ctx.message.channel.typing():
                    print(process.start_msg_id, process.end_msg_id)
                    if process.start_msg_id and process.end_msg_id:

                        start_msg = await ctx.message.channel.fetch_message(
                            process.start_msg_id
                        )
                        end_msg = await ctx.message.channel.fetch_message(
                            process.end_msg_id
                        )

                        msgs = await ctx.message.channel.history(
                            limit=250
                        ).flatten()

                        start_msg_ind = msgs.index(start_msg)
                        end_msg_ind = msgs.index(end_msg)

                        for i in range(end_msg_ind, start_msg_ind + 1):
                            await msgs[i].delete()
                            await asyncio.sleep(0.5)

                        embed = discord.Embed(
                            title="Bulk delete successful",
                            description="Successfully deleted "
                            f"{start_msg_ind - end_msg_ind + 1} "
                            "messages.",
                            color=TEXT_COLOR,
                        )
                        await ctx.send(embed=embed, delete_after=5)

                        # TODO: resolve blanket except
                        try:
                            await instruct.delete()
                        except Exception as e:
                            print(e)
                            pass

                    else:
                        embed = discord.Embed(
                            title="Bulk delete failed",
                            description="You have not specified a start and "
                            "end point. Please retry.",
                            color=TEXT_COLOR,
                        )
                        await ctx.send(embed=embed, delete_after=5)
                        await reaction.remove(ctx.message.author)
                        await self.perform_delete_process(
                            ctx, instruct, process
                        )

            elif str(reaction.emoji) == NO_REACT:
                self.delete_process_table.pop(ctx.message.channel.id)
                self.delete_process_table.commit()
                embed = discord.Embed(
                    title="Bulk delete failed",
                    description="Process timed out. Please retry.",
                    color=TEXT_COLOR,
                )
                await ctx.send(embed=embed, delete_after=5)
                await instruct.delete()

        except asyncio.TimeoutError:
            self.delete_process_table.pop(ctx.message.channel.id)
            self.delete_process_table.commit()
            embed = discord.Embed(
                title="Bulk delete failed",
                description="Process timed out. Please retry.",
                color=TEXT_COLOR,
            )
            await ctx.send(embed=embed, delete_after=5)
            await instruct.delete()

    @commands.Cog.listener()
    @commands.has_permissions(manage_messages=True)
    async def on_raw_reaction_add(self, payload):
        emoji = payload.emoji
        member = payload.member

        for doer_id, process in self.delete_process_table.items():
            if member.id == int(doer_id):
                if str(emoji) == "▶️":
                    process.start_msg_id = payload.message_id
                    self.delete_process_table[doer_id] = process
                    self.delete_process_table.commit()
                elif str(emoji) == "⏹️":
                    process.end_msg_id = payload.message_id
                    self.delete_process_table[doer_id] = process
                    self.delete_process_table.commit()


async def setup(bot):
    await bot.add_cog(MainCommands(bot))
