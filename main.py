import discord
from discord.ext import commands
import os
from keep_alive import keep_alive


class PrivateRoom:
    def __init__(self):
        self.guild_id = None
        self.owner_id = None
        self.private_voice_id = None
        self.private_text_id = None
        self.waiting_room_id = None


class DeleteProcess:
    def __init__(self):
        self.doer_id = None
        self.start_msg_id = None
        self.end_msg_id = None


intents = discord.Intents.default()
intents.members = True

prefix = 'pr!'
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

keep_alive()
bot.load_extension('new_main_comms')
bot.load_extension('preferencecommands')
# bot.load_extension('error_handler')
bot.run(os.environ['TOKEN'])