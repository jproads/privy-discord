import discord
from discord.ext import commands
import pickle



class Preferences(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.lobby_channel = ''
    self.lobby_category = ''
  
  def items(self):
    return {
      'lobby_channel': self.lobby_channel.id,
      'lobby_category': self.lobby_category.id
    }
  
  @commands.Cog.listener()
  async def on_ready(self):
    global prefList
    try:
      prefList = pickle.load(open("preferences.p", "rb"))
      print('Loaded preference.p successfully')
    except:
      prefList = dict()
      print('Error loading preferences.p')

  @commands.command(name='setlobby', aliases=['sl'])
  @commands.has_permissions(manage_channels=True)
  async def newLobby(self, ctx: commands.Context):
    if ctx.author.voice:
      try:
        prefList.pop(ctx.guild.id)
      except:
        pass
      self.lobby_channel = ctx.author.voice.channel
      self.lobby_category = ctx.author.voice.channel.category
      prefList.update({ctx.guild.id:self.items()})
  
      pickle.dump(prefList, open("preferences.p", "wb"))

      await ctx.send(f'Set {ctx.author.voice.channel} as the lobby!')
    
    else:
      await ctx.send('You need to be in a voice channel to use this!')      
  
  @commands.command(name='deleteLobby', aliases=['dl'])
  @commands.has_permissions(manage_channels=True)
  async def deleteLobby(self, ctx: commands.Context):
    try:
      prefList.pop(ctx.guild.id)
      await ctx.send(f"Erased this server's old lobby.")
      pickle.dump(prefList, open('preferences.p', 'wb'))
    except:
      pass
      await ctx.send('This server has no lobby!')
    


def setup(bot: commands.Bot):
  bot.add_cog(preferences(bot))
