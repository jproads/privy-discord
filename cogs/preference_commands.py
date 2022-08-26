from discord.ext import commands
from sqlitedict import SqliteDict

from constants import PRIVY_DB


class PreferenceCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lobby_channel = ""
        self.lobby_category = ""
        self.preference_table = SqliteDict()

    def items(self):
        return {
            "lobby_channel": self.lobby_channel.id,
            "lobby_category": self.lobby_category.id,
        }

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.preference_table = SqliteDict(
                PRIVY_DB, tablename="preferences"
            )
            print("Loaded preferences successfully")
        # TODO: fix bare except
        except Exception as e:
            self.preference_table = SqliteDict(
                PRIVY_DB, tablename="preferences"
            )
            print(f"Error loading preferences: {e}")

    @commands.command(name="setlobby", aliases=["sl"])
    @commands.has_permissions(manage_channels=True)
    async def new_lobby(self, ctx: commands.Context):
        if ctx.author.voice:
            try:
                self.preference_table.pop(ctx.guild.id)
            # TODO: fix bare except
            except Exception as e:
                print(f"Error creating lobby: {e}")
                pass
            self.lobby_channel = ctx.author.voice.channel
            self.lobby_category = ctx.author.voice.channel.category
            self.preference_table.update({ctx.guild.id: self.items()})

            self.preference_table.commit()

            await ctx.send(f"Set {ctx.author.voice.channel} as the lobby!")

        else:
            await ctx.send("You need to be in a voice channel to use this!")

    @commands.command(name="deleteLobby", aliases=["dl"])
    @commands.has_permissions(manage_channels=True)
    async def delete_lobby(self, ctx: commands.Context):
        try:
            self.preference_table.pop(ctx.guild.id)
            await ctx.send("Erased this server's old lobby.")
            self.preference_table.commit()
        # TODO: fix bare except
        except Exception as e:
            print(f"Error deleting lobby: {e}")
            pass
            await ctx.send("This server has no lobby!")


async def setup(bot):
    await bot.add_cog(PreferenceCommands(bot))
