import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class ServerLogs(commands.Cog):
    """Logs de eventos do servidor (avatar, banner, nome, etc)"""
    
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
    
    # ═══════════════ USER AVATAR/BANNER ═══════════════
    
    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Log de avatar/banner do usuário"""
        
        # Avatar
        if before.avatar != after.avatar:
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
                        "type": "avatar",
                        "old_url": str(before.avatar.url) if before.avatar else None,
                        "new_url": str(after.avatar.url) if after.avatar else None
                    }
                )
        
        # Banner
        if before.banner != after.banner:
            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if not member:
                    continue
                
                log_channel_id = await self.get_log_channel(guild.id, "avatar_update")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🎨 Banner atualizado",
                            description=f"{member.mention} trocou o banner do perfil",
                            color=discord.Color.purple(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                        
                        if before.banner:
                            embed.add_field(name="❌ Antes", value=f"[Banner antigo]({before.banner.url})", inline=True)
                        if after.banner:
                            embed.add_field(name="✅ Novo", value=f"[Banner atual]({after.banner.url})", inline=True)
                            embed.set_image(url=after.banner.url)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="avatar_update",
                    user_id=member.id,
                    data={
                        "user_name": str(member),
                        "type": "banner",
                        "old_url": str(before.banner.url) if before.banner else None,
                        "new_url": str(after.banner.url) if after.banner else None
                    }
                )
    
    # ═══════════════ SERVER ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Log de mudanças no servidor"""
        
        # Avatar do servidor
        if before.icon != after.icon:
            log_channel_id = await self.get_log_channel(after.id, "avatar_update")
            
            if log_channel_id:
                log_channel = after.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🖼️ Ícone do servidor atualizado",
                        description=f"Servidor **{after.name}**",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    if before.icon:
                        embed.set_thumbnail(url=before.icon.url)
                        embed.add_field(name="❌ Antes", value=f"[Ícone antigo]({before.icon.url})", inline=True)
                    if after.icon:
                        embed.set_image(url=after.icon.url)
                        embed.add_field(name="✅ Novo", value=f"[Ícone atual]({after.icon.url})", inline=True)
                    
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=after.id,
                log_type="avatar_update",
                data={
                    "server_name": after.name,
                    "type": "server_icon",
                    "old_url": str(before.icon.url) if before.icon else None,
                    "new_url": str(after.icon.url) if after.icon else None
                }
            )
        
        # Banner do servidor
        if before.banner != after.banner:
            log_channel_id = await self.get_log_channel(after.id, "avatar_update")
            
            if log_channel_id:
                log_channel = after.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🎨 Banner do servidor atualizado",
                        description=f"Servidor **{after.name}**",
                        color=discord.Color.purple(),
                        timestamp=discord.utils.utcnow()
                    )
                    if before.banner:
                        embed.add_field(name="❌ Antes", value=f"[Banner antigo]({before.banner.url})", inline=True)
                    if after.banner:
                        embed.add_field(name="✅ Novo", value=f"[Banner atual]({after.banner.url})", inline=True)
                        embed.set_image(url=after.banner.url)
                    
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=after.id,
                log_type="avatar_update",
                data={
                    "server_name": after.name,
                    "type": "server_banner",
                    "old_url": str(before.banner.url) if before.banner else None,
                    "new_url": str(after.banner.url) if after.banner else None
                }
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogs(bot))