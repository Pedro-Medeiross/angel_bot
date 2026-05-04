import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class InviteLogs(commands.Cog):
    """Logs de criação e deleção de invites"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.log_api = log_api
        self._invite_cache = {}  # guild_id: {invite_code: invite_object}
    
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
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache inicial de invites"""
        for guild in self.bot.guilds:
            if guild.me.guild_permissions.manage_guild:
                try:
                    invites = await guild.invites()
                    self._invite_cache[guild.id] = {
                        invite.code: invite for invite in invites
                    }
                except discord.Forbidden:
                    self._invite_cache[guild.id] = {}
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Log de invite criado"""
        
        # Atualiza cache
        if invite.guild.id not in self._invite_cache:
            self._invite_cache[invite.guild.id] = {}
        self._invite_cache[invite.guild.id][invite.code] = invite
        
        log_channel_id = await self.get_log_channel(invite.guild.id, "log_invites")
        
        if log_channel_id:
            log_channel = invite.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🔗 Convite criado",
                    description=f"Novo convite criado por {invite.inviter.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=invite.inviter.display_name, icon_url=invite.inviter.display_avatar.url)
                embed.set_footer(text=f"ID: {invite.inviter.id} | @{invite.inviter.name}")
                
                embed.add_field(name="📝 Código", value=invite.code, inline=True)
                embed.add_field(name="📢 Canal", value=invite.channel.mention, inline=True)
                
                if invite.max_uses:
                    embed.add_field(name="🔢 Máximo de usos", value=str(invite.max_uses), inline=True)
                else:
                    embed.add_field(name="🔢 Máximo de usos", value="Ilimitado", inline=True)
                
                if invite.max_age:
                    if invite.max_age == 0:
                        embed.add_field(name="⏰ Expira em", value="Nunca", inline=True)
                    else:
                        hours = invite.max_age // 3600
                        embed.add_field(name="⏰ Expira em", value=f"{hours}h", inline=True)
                else:
                    embed.add_field(name="⏰ Expira em", value="Nunca", inline=True)
                
                if invite.temporary:
                    embed.add_field(name="🔄 Temporário", value="Sim (membro sai ao perder acesso)", inline=False)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=invite.guild.id,
            log_type="log_invites",
            user_id=invite.inviter.id,
            channel_id=invite.channel.id,
            data={
                "action": "create",
                "invite_code": invite.code,
                "inviter_name": invite.inviter.name,
                "inviter_display_name": invite.inviter.display_name,
                "channel_name": invite.channel.name,
                "channel_id": str(invite.channel.id),
                "max_uses": invite.max_uses,
                "max_age_seconds": invite.max_age,
                "temporary": invite.temporary
            }
        )
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Log de invite deletado"""
        
        # Remove do cache
        if invite.guild.id in self._invite_cache:
            self._invite_cache[invite.guild.id].pop(invite.code, None)
        
        log_channel_id = await self.get_log_channel(invite.guild.id, "log_invites")
        
        if log_channel_id:
            log_channel = invite.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Convite deletado",
                    description=f"Convite `{invite.code}` foi removido",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                
                if invite.inviter:
                    embed.set_author(name=invite.inviter.display_name, icon_url=invite.inviter.display_avatar.url)
                
                embed.add_field(name="📝 Código", value=invite.code, inline=True)
                embed.add_field(name="📢 Canal", value=invite.channel.mention if invite.channel else "Desconhecido", inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=invite.guild.id,
            log_type="log_invites",
            user_id=invite.inviter.id if invite.inviter else None,
            channel_id=invite.channel.id if invite.channel else None,
            data={
                "action": "delete",
                "invite_code": invite.code,
                "inviter_name": invite.inviter.name if invite.inviter else None,
                "inviter_display_name": invite.inviter.display_name if invite.inviter else None,
                "channel_name": invite.channel.name if invite.channel else None,
                "channel_id": str(invite.channel.id) if invite.channel else None
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteLogs(bot))