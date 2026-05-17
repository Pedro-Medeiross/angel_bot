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
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.log_api = log_api
        self._invite_cache: dict[int, dict[str, discord.Invite]] = {}
    
    async def _get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/log-channel/{log_type}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("channel_id")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao consultar API: {e}")
        return None
    
    def _build_invite_embed(self, invite: discord.Invite, title: str, color: discord.Color,
                            extra_fields: dict = None) -> discord.Embed:
        """Cria embed base para logs de invite"""
        description = f"Novo convite criado por {invite.inviter.mention}" if invite.inviter else f"Convite `{invite.code}` foi removido"
        
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        
        if invite.inviter:
            embed.set_author(name=invite.inviter.display_name, icon_url=invite.inviter.display_avatar.url)
        
        embed.add_field(name="📝 Código", value=invite.code, inline=True)
        embed.add_field(name="📢 Canal", value=invite.channel.mention if invite.channel else "Desconhecido", inline=True)
        
        if extra_fields:
            for name, value in extra_fields.items():
                embed.add_field(name=name, value=value, inline=True)
        
        return embed
    
    def _build_invite_data(self, invite: discord.Invite, action: str) -> dict:
        """Cria dados base para envio à API"""
        return {
            "action": action,
            "invite_code": invite.code,
            "inviter_name": invite.inviter.name if invite.inviter else None,
            "inviter_display_name": invite.inviter.display_name if invite.inviter else None,
            "channel_name": invite.channel.name if invite.channel else None,
            "channel_id": str(invite.channel.id) if invite.channel else None,
        }
    
    # ═══════════════ CACHE ═══════════════
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache inicial de invites"""
        for guild in self.bot.guilds:
            if guild.me.guild_permissions.manage_guild:
                try:
                    invites = await guild.invites()
                    self._invite_cache[guild.id] = {inv.code: inv for inv in invites}
                except discord.Forbidden:
                    self._invite_cache[guild.id] = {}
    
    # ═══════════════ INVITE CREATE ═══════════════
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        self._invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite
        
        log_channel_id = await self._get_log_channel(invite.guild.id, "log_invites")
        
        if log_channel_id:
            log_channel = invite.guild.get_channel(log_channel_id)
            if log_channel:
                extra = {}
                extra["🔢 Máximo de usos"] = str(invite.max_uses) if invite.max_uses else "Ilimitado"
                
                if invite.max_age:
                    extra["⏰ Expira em"] = "Nunca" if invite.max_age == 0 else f"{invite.max_age // 3600}h"
                else:
                    extra["⏰ Expira em"] = "Nunca"
                
                if invite.temporary:
                    extra["🔄 Temporário"] = "Sim (membro sai ao perder acesso)"
                
                embed = self._build_invite_embed(invite, "🔗 Convite criado", discord.Color.green(), extra)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=invite.guild.id, log_type="log_invites",
            user_id=invite.inviter.id, channel_id=invite.channel.id,
            data={
                **self._build_invite_data(invite, "create"),
                "max_uses": invite.max_uses, "max_age_seconds": invite.max_age, "temporary": invite.temporary
            }
        )
    
    # ═══════════════ INVITE DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild.id in self._invite_cache:
            self._invite_cache[invite.guild.id].pop(invite.code, None)
        
        log_channel_id = await self._get_log_channel(invite.guild.id, "log_invites")
        
        if log_channel_id:
            log_channel = invite.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_invite_embed(invite, "🗑️ Convite deletado", discord.Color.red())
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=invite.guild.id, log_type="log_invites",
            user_id=invite.inviter.id if invite.inviter else None,
            channel_id=invite.channel.id if invite.channel else None,
            data=self._build_invite_data(invite, "delete")
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteLogs(bot))