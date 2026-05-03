import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class ServerLogs(commands.Cog):
    """Logs de avatar do usuário"""
    
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
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Log de avatar do usuário"""
        
        if before.avatar == after.avatar:
            return
        
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if not member:
                continue
            
            log_channel_id = await self.get_log_channel(guild.id, "avatar_update")
            
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🖼️ Avatar atualizado",
                        description=f"{member.mention} trocou de avatar",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=str(member), icon_url=after.display_avatar.url)
                    embed.set_footer(text=f"ID: {member.id}")
                    embed.set_thumbnail(url=after.display_avatar.url)
                    
                    if before.avatar:
                        embed.add_field(name="❌ Antes", value=f"[Avatar antigo]({before.avatar.url})", inline=True)
                    embed.add_field(name="✅ Novo", value=f"[Avatar atual]({after.avatar.url})", inline=True)
                    
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=guild.id,
                log_type="avatar_update",
                user_id=member.id,
                data={
                    "user_name": str(member),
                    "old_url": str(before.avatar.url) if before.avatar else None,
                    "new_url": str(after.avatar.url) if after.avatar else None
                }
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogs(bot))