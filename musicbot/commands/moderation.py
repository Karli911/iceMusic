import discord
from discord.ext import commands
from datetime import datetime

def has_moderation_permissions():
    async def predicate(ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        if ctx.author.guild_permissions.administrator:
            return True
        return False
    return commands.check(predicate)

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warns = {}

    @commands.command(name='ban')
    @has_moderation_permissions()
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Ban a member from the server"""
        try:
            await member.ban(reason=reason)
            await ctx.send(f'{member.mention} has been banned for: {reason}')
        except discord.Forbidden:
            await ctx.send('I do not have permission to ban this member.')
        except discord.HTTPException:
            await ctx.send('Banning the member failed.')

    @commands.command(name='kick')
    @has_moderation_permissions()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kick a member from the server"""
        try:
            await member.kick(reason=reason)
            await ctx.send(f'{member.mention} has been kicked for: {reason}')
        except discord.Forbidden:
            await ctx.send('I do not have permission to kick this member.')
        except discord.HTTPException:
            await ctx.send('Kicking the member failed.')

    @commands.command(name='mute')
    @has_moderation_permissions()
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        """Mute a member in the server (chat only)"""
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_role, speak=False, send_messages=False)
        
        await member.add_roles(mute_role, reason=reason)
        await ctx.send(f'{member.mention} has been muted for: {reason}')

    @commands.command(name='unmute')
    @has_moderation_permissions()
    async def unmute(self, ctx, member: discord.Member):
        """Unmute a member in the server (chat only)"""
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        await member.remove_roles(mute_role)
        await ctx.send(f'{member.mention} has been unmuted.')

    @commands.command(name='warn')
    @has_moderation_permissions()
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        """Warn a member in the server"""
        if member.id not in self.warns:
            self.warns[member.id] = []
        self.warns[member.id].append({"reason": reason, "timestamp": datetime.utcnow()})
        await ctx.send(f'{member.mention} has been warned for: {reason}')

    @commands.command(name='warns')
    @has_moderation_permissions()
    async def warns(self, ctx, member: discord.Member):
        """List all warnings for a member"""
        if member.id not in self.warns or len(self.warns[member.id]) == 0:
            await ctx.send(f'{member.mention} has no warnings.')
        else:
            warnings = self.warns[member.id]
            warn_list = [f"{idx+1}. Reason: {warn['reason']} - Timestamp: {warn['timestamp']}" for idx, warn in enumerate(warnings)]
            await ctx.send(f'Warnings for {member.mention}:\n' + '\n'.join(warn_list))

    @commands.command(name='purge')
    @has_moderation_permissions()
    async def purge(self, ctx, limit: int):
        """Purge a specified number of messages from the channel"""
        await ctx.channel.purge(limit=limit)
        await ctx.send(f'Purged {limit} messages.', delete_after=5)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
