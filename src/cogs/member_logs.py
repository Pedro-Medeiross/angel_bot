import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class MemberLogs(commands.Cog):
    """Logs de eventos de membro (timeout, ban, unban)"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.log_api = log_api
    
    async def get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/log-channel/{log_type}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("channel_id")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao consultar API: {e}")
        return None
    
    async def get_moderator(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> str | None:
        """Busca o moderador no audit log"""
        try:
            async for entry in guild.audit_logs(limit=3, action=action):
                if entry.target and entry.target.id == target_id:
                    return str(entry.user)
        except discord.Forbidden:
            pass
        return None
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log de timeout"""
        
        # Timeout (via bot/API)
        if before.timed_out != after.timed_out:
            log_channel_id = await self.get_log_channel(after.guild.id, "member_timeout")
            
            moderator = await self.get_moderator(
                after.guild,
                after.id,
                discord.AuditLogAction.member_update
            )
            
            if after.timed_out:
                timeout_until = after.communication_disabled_until
                
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 Membro silenciado (timeout)",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id} | @{after.name}")
                        
                        embed.add_field(name="👤 Membro", value=after.mention, inline=True)
                        if moderator:
                            embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                        
                        if timeout_until:
                            embed.add_field(
                                name="⏰ Expira",
                                value=discord.utils.format_dt(timeout_until, 'R'),
                                inline=False
                            )
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    target_id=after.id,
                    data={
                        "user_name": after.name,
                        "display_name": after.display_name,
                        "moderator_name": moderator,
                        "action": "applied",
                        "expires_at": timeout_until.isoformat() if timeout_until else None
                    }
                )
            else:
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔊 Membro des-silenciado",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id} | @{after.name}")
                        
                        embed.add_field(name="👤 Membro", value=after.mention, inline=True)
                        if moderator:
                            embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    target_id=after.id,
                    data={
                        "user_name": after.name,
                        "display_name": after.display_name,
                        "moderator_name": moderator,
                        "action": "removed"
                    }
                )
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Log de membro banido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_ban")
        
        moderator = None
        reason = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
                if entry.target and entry.target.id == user.id:
                    moderator = str(entry.user)
                    reason = entry.reason or "Nenhuma razão informada"
                    break
        except discord.Forbidden:
            pass
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🔨 Membro banido",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=user.global_name or user.name, icon_url=user.display_avatar.url)
                embed.set_footer(text=f"ID: {user.id} | @{user.name}")
                
                embed.add_field(name="👤 Usuário", value=f"{user.name}", inline=True)
                if moderator:
                    embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                if reason:
                    embed.add_field(name="📝 Motivo", value=reason, inline=False)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_ban",
            target_id=user.id,
            data={
                "user_name": user.name,
                "display_name": user.global_name,
                "moderator_name": moderator,
                "reason": reason
            }
        )
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log de membro desbanido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_unban")
        
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.unban):
                if entry.target and entry.target.id == user.id:
                    moderator = str(entry.user)
                    break
        except discord.Forbidden:
            pass
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🔓 Membro desbanido",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=user.global_name or user.name, icon_url=user.display_avatar.url)
                embed.set_footer(text=f"ID: {user.id} | @{user.name}")
                
                embed.add_field(name="👤 Usuário", value=f"{user.name}", inline=True)
                if moderator:
                    embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_unban",
            target_id=user.id,
            data={
                "user_name": user.name,
                "display_name": user.global_name,
                "moderator_name": moderator
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogs(bot))