import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class MemberLogs(commands.Cog):
    """Logs de eventos de membro"""
    
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
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log de mudanças no membro (nickname, roles, timeout)"""
        
        # Nickname
        if before.nick != after.nick:
            log_channel_id = await self.get_log_channel(after.guild.id, "member_nickname")
            
            if log_channel_id:
                log_channel = after.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="📝 Apelido alterado",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                    embed.set_footer(text=f"ID: {after.id}")
                    
                    old_nick = before.nick or str(before)
                    new_nick = after.nick or str(after)
                    
                    embed.add_field(name="❌ Antes", value=old_nick, inline=True)
                    embed.add_field(name="✅ Depois", value=new_nick, inline=True)
                    
                    embed.description = f"{after.mention} alterou o apelido"
                    
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=after.guild.id,
                log_type="member_nickname",
                user_id=after.id,
                data={
                    "user_name": str(after),
                    "old_nickname": before.nick or str(before),
                    "new_nickname": after.nick or str(after)
                }
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogs(bot))