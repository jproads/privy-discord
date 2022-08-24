from sqlitedict import SqliteDict
from discord.ext import commands
import pickle


class PreferenceCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lobby_channel = ''
        self.lobby_category = ''
        self.preference_db = SqliteDict()

    def items(self):
        return {
            'lobby_channel': self.lobby_channel.id,
            'lobby_category': self.lobby_category.id
        }

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.preference_db = SqliteDict('databases/preference_db.sqlite')
            print('Loaded preferences successfully')
        except:
            self.preference_db = SqliteDict('databases/preference_db.sqlite')
            print('Error loading preferences')

    @commands.command(name='setlobby', aliases=['sl'])
    @commands.has_permissions(manage_channels=True)
    async def new_lobby(self, ctx: commands.Context):
        if ctx.author.voice:
            try:
                self.preference_db.pop(ctx.guild.id)
            except:
                pass
            self.lobby_channel = ctx.author.voice.channel
            self.lobby_category = ctx.author.voice.channel.category
            self.preference_db.update({ctx.guild.id: self.items()})

            self.preference_db.commit()

            await ctx.send(f'Set {ctx.author.voice.channel} as the lobby!')

        else:
            await ctx.send('You need to be in a voice channel to use this!')

    @commands.command(name='deleteLobby', aliases=['dl'])
    @commands.has_permissions(manage_channels=True)
    async def delete_lobby(self, ctx: commands.Context):
        try:
            self.preference_db.pop(ctx.guild.id)
            await ctx.send(f"Erased this server's old lobby.")
            self.preference_db.commit()
        except:
            pass
            await ctx.send('This server has no lobby!')


async def setup(bot):
    await bot.add_cog(PreferenceCommands(bot))