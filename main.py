import discord
from discord.ext import commands
# from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

prefix = 'pr!'


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(intents=intents, command_prefix=prefix, help_command=None)
        self.initial_extensions = [
            'cogs.main_commands',
            'cogs.preference_commands',
        ]

    async def setup_hook(self):
        for ext in self.initial_extensions:
            await self.load_extension(ext)

    async def close(self):
        await super().close()

    async def on_ready(self):
        print('Ready!')


bot = MyBot()
bot.run('OTAxODM3NjMxNzQ1MzE4OTcy.GeAelS._OVHbV0YXbqVjOMxce6eVV61Y45kN-P_LYK5aM')
