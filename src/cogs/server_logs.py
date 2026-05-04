import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class ServerLogs(commands.Cog):
    """Logs de avatar, display name e username do usuário"""
    
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
        """Log de avatar, display name e username"""
        
        # Avatar
        if before.avatar != after.avatar:
            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if not member:
                    continue
                if member.bot:
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
                        embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id} | @{after.name}")
                        embed.set_thumbnail(url=after.display_avatar.url)
                        
                        if before.avatar:
                            embed.add_field(name="❌ Antes", value=f"[Avatar antigo]({before.avatar.url})", inline=True)
                        embed.add_field(name="✅ Novo", value=f"[Avatar atual]({after.avatar.url})", inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="avatar_update",
                    user_id=after.id,
                    data={
                        "user_name": after.name,
                        "display_name": after.global_name,
                        "user_avatar": str(after.display_avatar.url),
                        "type": "avatar",
                        "old_url": str(before.avatar.url) if before.avatar else None,
                        "new_url": str(after.avatar.url) if after.avatar else None
                    }
                )
        
        # Display name global
        if before.global_name != after.global_name:
            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if not member:
                    continue
                if member.bot:
                    continue
                
                log_channel_id = await self.get_log_channel(guild.id, "nickname_change")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        old_name = before.global_name or before.name
                        new_name = after.global_name or after.name
                        
                        embed = discord.Embed(
                            title="📝 Nome de exibição alterado",
                            description=f"{member.mention} alterou o nome de exibição",
                            color=discord.Color.orange(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id} | @{after.name}")
                        embed.set_thumbnail(url=after.display_avatar.url)
                        
                        embed.add_field(name="❌ Antes", value=old_name, inline=True)
                        embed.add_field(name="✅ Depois", value=new_name, inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="nickname_change",
                    user_id=after.id,
                    data={
                        "user_name": after.name,
                        "display_name": after.global_name,
                        "user_avatar": str(after.display_avatar.url),
                        "type": "display_name",
                        "old_name": before.global_name or before.name,
                        "new_name": after.global_name or after.name
                    }
                )
        
        # Username
        if before.name != after.name:
            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if not member:
                    continue
                if member.bot:
                    continue
                
                log_channel_id = await self.get_log_channel(guild.id, "nickname_change")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🏷️ Nome de usuário alterado",
                            description=f"{member.mention} alterou o nome de usuário",
                            color=discord.Color.yellow(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id}")
                        embed.set_thumbnail(url=after.display_avatar.url)
                        
                        embed.add_field(name="❌ Antes", value=f"@{before.name}", inline=True)
                        embed.add_field(name="✅ Depois", value=f"@{after.name}", inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="nickname_change",
                    user_id=after.id,
                    data={
                        "user_name": after.name,
                        "display_name": after.global_name,
                        "user_avatar": str(after.display_avatar.url),
                        "type": "username",
                        "old_name": before.name,
                        "new_name": after.name
                    }
                )

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogs(bot))