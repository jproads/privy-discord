import discord
from discord.ext import commands
import os
# from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True

prefix = 'pr!'
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

# keep_alive()
async def main():
    await bot.load_extension('main_commands')
    await bot.load_extension('preference_commands')
# bot.load_extension('error_handler')


bot.run("OTAxODM3NjMxNzQ1MzE4OTcy.GeAelS._OVHbV0YXbqVjOMxce6eVV61Y45kN-P_LYK5aM") # Does not work in non-repl environment
