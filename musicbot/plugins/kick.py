import discord
from discord.ext import commands

def has_kick_permissions():
  async def predicate(ctx):
    if await ctx.bot.is_owner(ctx.author):
      return True
    if ctx.author.guild_permissions.kick_members:
      return True
    return False
  return commands.check(predicate)

class kickCog(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command(name = "kick")
  @has_kick_permissions()
  async def kick(self, ctx, member: discord.Member, *, reason = reason):
    try:
      await member.kick(reason=reason)
      await ctx.send(f'{member.mention} has been kicked for: {reason}")
    except discord.Forbidden:
      await ctx.send("I do not have permission to kick this member.")
    except discord.HTTPException:
      await ctx.send("Kicking the member failed.")
  
  @kick.error
  async def kick_error(self, ctx, error):
    if isinstance(error, commands.CheckFailure):
      await ctx.send("You do not have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
      await ctx.send("Please specify a member to kick.")
    else:
      await ctx.send("An error occurred.")
asyc def setup(bot):
  await bot.add_cog(kickCog(bot))

       
      
