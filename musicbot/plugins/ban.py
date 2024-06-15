import discord
from discord.ext import commands
from musicbot.bot import MusicBot

def has_permissions_or_role():
  async def predicate(ctx):
    if await ctx.bot.is_owner(ctx.author):
      return True
    if ctx.author.guild_permissions.administrator:
      return True
    moderator_role = discord.utils.get(ctx.guild.roles, name = "Moderator")
    if moderator_role in ctx.author.roles:
      return True
    return False
  return commands.check(predicate)

class BanCog(commands.Cog):
  def __init__(self,bot: MusicBot):
    self.bot = bot
  @commands.command(name = "ban")
  @has_permissions_or_role()
  async def ban(self, ctx, member: discord.Member, *, reason=None):
  """Ban member from the server"""
    try:
      await member.ban(reason=reason)
      await ctx.send(f"{member.mention} has been banned for: {reason}")
    except discord.Forbidden:
      await ctx.send("I do not have permission to ban this member")
    except discord.HTTPException:
      await ctx.send("Banning the member failed due to API errors.")
  @ban.error
  async def ban_error(self, ctx, error):
    if instance(error, commands.CheckFailure):
      await ctx.send("You do not have permissions to use this command.")
    elif instance(error, MissingRequiredArgument):
      await ctx.send("Please specify a member to ban.")
    else:
      await ctx.send("An error occurred.")
async def setup(bot):
  await bot.add_cog(BanCog(bot))
      
  
