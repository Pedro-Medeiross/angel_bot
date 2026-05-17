import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class MemberEvents(commands.Cog):
    """Logs de entrada e saída de membros"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.log_api = log_api
    
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
    
    def _build_member_embed(self, member: discord.Member, title: str, description: str,
                            color: discord.Color) -> discord.Embed:
        """Cria embed base para logs de membro"""
        embed = discord.Embed(
            title=title, description=description, color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} | @{member.name}")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 Username", value=member.name, inline=True)
        embed.add_field(name="📝 Display", value=member.display_name, inline=True)
        return embed
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log_channel_id = await self._get_log_channel(member.guild.id, "member_join")
        account_age = (discord.utils.utcnow() - member.created_at).days
        
        if log_channel_id:
            log_channel = member.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_member_embed(
                    member, "👋 Membro entrou",
                    f"{member.mention} entrou no servidor",
                    discord.Color.green()
                )
                embed.add_field(name="📅 Conta criada", value=f"{discord.utils.format_dt(member.created_at, 'R')} ({account_age} dias)", inline=True)
                embed.add_field(name="👥 Total de membros", value=member.guild.member_count, inline=True)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=member.guild.id, log_type="member_join", target_id=member.id,
            data={
                "user_name": member.name, "display_name": member.display_name,
                "user_avatar": str(member.display_avatar.url),
                "account_created": member.created_at.isoformat(),
                "account_age_days": account_age, "member_count": member.guild.member_count
            }
        )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel_id = await self._get_log_channel(member.guild.id, "member_leave")
        
        if log_channel_id:
            log_channel = member.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_member_embed(
                    member, "🚪 Membro saiu",
                    f"{member.mention} saiu do servidor",
                    discord.Color.red()
                )
                
                if member.joined_at:
                    time_in_server = (discord.utils.utcnow() - member.joined_at).days
                    embed.add_field(name="📅 Entrou em", value=discord.utils.format_dt(member.joined_at, 'R'), inline=True)
                    embed.add_field(name="⏱️ Tempo no servidor", value=f"{time_in_server} dias", inline=True)
                
                roles = [role.mention for role in member.roles if role.name != "@everyone"]
                if roles:
                    embed.add_field(name=f"👔 Cargos ({len(roles)})", value=" ".join(roles[:10]), inline=False)
                
                embed.add_field(name="👥 Total de membros", value=member.guild.member_count, inline=True)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=member.guild.id, log_type="member_leave", target_id=member.id,
            data={
                "user_name": member.name, "display_name": member.display_name,
                "user_avatar": str(member.display_avatar.url),
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "roles": [{"name": r.name, "id": str(r.id)} for r in member.roles if r.name != "@everyone"],
                "member_count": member.guild.member_count
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))