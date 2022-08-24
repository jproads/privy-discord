import discord
from discord.ext import commands
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True

prefix = 'pr!'
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

keep_alive()
bot.load_extension('new_main_comms')
bot.load_extension('preferencecommands')
# bot.load_extension('error_handler')
bot.run(os.environ['TOKEN']) # Does not work in non-repl environment
