import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class ChannelLogs(commands.Cog):
    """Logs de criação, edição e deleção de canais"""
    
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
    
    def _channel_type_name(self, channel: discord.abc.GuildChannel) -> str:
        """Retorna nome amigável do tipo de canal"""
        type_map = {
            discord.ChannelType.text: "Texto",
            discord.ChannelType.voice: "Voz",
            discord.ChannelType.category: "Categoria",
            discord.ChannelType.stage_voice: "Palco",
            discord.ChannelType.forum: "Fórum",
            discord.ChannelType.news: "Anúncios",
        }
        return type_map.get(channel.type, str(channel.type))
    
    # ═══════════════ CHANNEL CREATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log de canal criado"""
        
        log_channel_id = await self.get_log_channel(channel.guild.id, "channel_create")
        
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="📢 Canal criado",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="📛 Nome", value=channel.name, inline=True)
                embed.add_field(name="🆔 ID", value=channel.id, inline=True)
                embed.add_field(name="📋 Tipo", value=self._channel_type_name(channel), inline=True)
                
                if hasattr(channel, 'category') and channel.category:
                    embed.add_field(name="📁 Categoria", value=channel.category.name, inline=True)
                
                if isinstance(channel, discord.TextChannel) and channel.topic:
                    embed.add_field(name="📝 Tópico", value=channel.topic[:1024], inline=False)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=channel.guild.id,
            log_type="channel_create",
            channel_id=channel.id,
            data={
                "channel_name": channel.name,
                "channel_id": str(channel.id),
                "channel_type": str(channel.type),
                "channel_type_name": self._channel_type_name(channel),
                "category_name": channel.category.name if hasattr(channel, 'category') and channel.category else None,
                "category_id": str(channel.category.id) if hasattr(channel, 'category') and channel.category else None,
                "topic": channel.topic if isinstance(channel, discord.TextChannel) else None,
                "position": channel.position
            }
        )
    
    # ═══════════════ CHANNEL DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log de canal deletado"""
        
        log_channel_id = await self.get_log_channel(channel.guild.id, "channel_delete")
        
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Canal deletado",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="📛 Nome", value=channel.name, inline=True)
                embed.add_field(name="🆔 ID", value=channel.id, inline=True)
                embed.add_field(name="📋 Tipo", value=self._channel_type_name(channel), inline=True)
                
                if hasattr(channel, 'category') and channel.category:
                    embed.add_field(name="📁 Categoria", value=channel.category.name, inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=channel.guild.id,
            log_type="channel_delete",
            channel_id=channel.id,
            data={
                "channel_name": channel.name,
                "channel_id": str(channel.id),
                "channel_type": str(channel.type),
                "channel_type_name": self._channel_type_name(channel),
                "category_name": channel.category.name if hasattr(channel, 'category') and channel.category else None,
                "category_id": str(channel.category.id) if hasattr(channel, 'category') and channel.category else None,
                "position": channel.position
            }
        )
    
    # ═══════════════ CHANNEL UPDATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Log de canal editado"""
        
        log_channel_id = await self.get_log_channel(after.guild.id, "channel_update")
        
        if not log_channel_id:
            return
        
        log_channel = after.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes = {}
        
        # Nome
        if before.name != after.name:
            changes["name"] = {"old": before.name, "new": after.name}
        
        # Tópico (apenas canais de texto)
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                changes["topic"] = {"old": before.topic, "new": after.topic}
            
            # Slowmode
            if before.slowmode_delay != after.slowmode_delay:
                changes["slowmode"] = {"old": before.slowmode_delay, "new": after.slowmode_delay}
            
            # NSFW
            if before.nsfw != after.nsfw:
                changes["nsfw"] = {"old": before.nsfw, "new": after.nsfw}
        
        # Bitrate (apenas canais de voz)
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            if before.bitrate != after.bitrate:
                changes["bitrate"] = {"old": before.bitrate, "new": after.bitrate}
            
            if before.user_limit != after.user_limit:
                changes["user_limit"] = {"old": before.user_limit, "new": after.user_limit}
        
        # Posição
        if before.position != after.position:
            changes["position"] = {"old": before.position, "new": after.position}
        
        # Categoria
        old_cat = before.category.name if hasattr(before, 'category') and before.category else None
        new_cat = after.category.name if hasattr(after, 'category') and after.category else None
        if old_cat != new_cat:
            changes["category"] = {"old": old_cat, "new": new_cat}
        
        # Permissões (overwrites)
        before_overwrites = {str(target.id): overwrite for target, overwrite in before.overwrites.items()}
        after_overwrites = {str(target.id): overwrite for target, overwrite in after.overwrites.items()}
        if before_overwrites != after_overwrites:
            changes["permissions"] = {"old": len(before_overwrites), "new": len(after_overwrites)}
        
        if not changes:
            return
        
        # Embed
        embed = discord.Embed(
            title="✏️ Canal editado",
            description=f"Canal {after.mention}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        for key, value in changes.items():
            name_map = {
                "name": "📛 Nome",
                "topic": "📝 Tópico",
                "slowmode": "⏱️ Slowmode",
                "nsfw": "🔞 NSFW",
                "bitrate": "🎵 Bitrate",
                "user_limit": "👥 Limite de usuários",
                "position": "🔢 Posição",
                "category": "📁 Categoria",
                "permissions": "🔒 Permissões"
            }
            embed.add_field(
                name=name_map.get(key, key),
                value=f"❌ {value['old']}\n✅ {value['new']}",
                inline=True
            )
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=after.guild.id,
            log_type="channel_update",
            channel_id=after.id,
            data={
                "channel_name": after.name,
                "channel_id": str(after.id),
                "channel_type": str(after.type),
                "channel_type_name": self._channel_type_name(after),
                "changes": changes
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLogs(bot))