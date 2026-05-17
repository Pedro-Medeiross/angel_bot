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
    
    def _build_user_embed(self, user: discord.User, title: str, description: str,
                          color: discord.Color, show_username: bool = True) -> discord.Embed:
        """Cria embed base para logs de usuário"""
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id}" + (f" | @{user.name}" if show_username else ""))
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed
    
    def _build_user_data(self, user: discord.User, extra: dict = None) -> dict:
        """Dados base do usuário para API"""
        data = {
            "user_name": user.name,
            "display_name": user.global_name,
            "user_avatar": str(user.display_avatar.url),
        }
        if extra:
            data.update(extra)
        return data
    
    async def _notify_all_guilds(self, user: discord.User, log_type: str, build_embed_fn, build_data_fn):
        """Notifica todas as guilds sobre uma mudança no usuário"""
        for guild in self.bot.guilds:
            member = guild.get_member(user.id)
            if not member or member.bot:
                continue
            
            log_channel_id = await self._get_log_channel(guild.id, log_type)
            
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    embed = build_embed_fn(member, user)
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=guild.id, log_type=log_type, user_id=user.id,
                data=build_data_fn(user)
            )
    
    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.avatar != after.avatar:
            await self._notify_all_guilds(after, "avatar_update",
                lambda m, u: self._build_avatar_embed(m, u, before),
                lambda u: self._build_user_data(u, {
                    "type": "avatar",
                    "old_url": str(before.avatar.url) if before.avatar else None,
                    "new_url": str(after.avatar.url) if after.avatar else None
                })
            )
        
        if before.global_name != after.global_name:
            await self._notify_all_guilds(after, "nickname_change",
                lambda m, u: self._build_name_embed(m, u, before.global_name or before.name, after.global_name or after.name,
                                                     "📝 Nome de exibição alterado", f"{m.mention} alterou o nome de exibição", discord.Color.orange()),
                lambda u: self._build_user_data(u, {
                    "type": "display_name",
                    "old_name": before.global_name or before.name,
                    "new_name": after.global_name or after.name
                })
            )
        
        if before.name != after.name:
            await self._notify_all_guilds(after, "nickname_change",
                lambda m, u: self._build_name_embed(m, u, f"@{before.name}", f"@{after.name}",
                                                     "🏷️ Nome de usuário alterado", f"{m.mention} alterou o nome de usuário", discord.Color.yellow()),
                lambda u: self._build_user_data(u, {
                    "type": "username",
                    "old_name": before.name,
                    "new_name": after.name
                })
            )
    
    def _build_avatar_embed(self, member: discord.Member, user: discord.User, before: discord.User) -> discord.Embed:
        embed = self._build_user_embed(user, "🖼️ Avatar atualizado", f"{member.mention} trocou de avatar", discord.Color.blue())
        if before.avatar:
            embed.add_field(name="❌ Antes", value=f"[Avatar antigo]({before.avatar.url})", inline=True)
        embed.add_field(name="✅ Novo", value=f"[Avatar atual]({user.avatar.url})", inline=True)
        return embed
    
    def _build_name_embed(self, member: discord.Member, user: discord.User, old_name: str, new_name: str,
                           title: str, description: str, color: discord.Color) -> discord.Embed:
        embed = self._build_user_embed(user, title, description, color, show_username=(title == "📝 Nome de exibição alterado"))
        embed.add_field(name="❌ Antes", value=old_name, inline=True)
        embed.add_field(name="✅ Depois", value=new_name, inline=True)
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogs(bot))