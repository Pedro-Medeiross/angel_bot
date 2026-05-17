import discord
from discord.ext import commands
import asyncio
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class ChannelLogs(commands.Cog):
    """Logs de criação, edição e deleção de canais"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.log_api = log_api
        self._position_queue: dict = {}
        self._position_task: dict = {}
        self._ignored_categories: dict[int, set] = {}
    
    # ═══════════════ HELPERS ═══════════════
    
    async def _get_ignored_categories(self, guild_id: int) -> set[int]:
        """Busca categorias de ticket para ignorar nos logs"""
        if guild_id in self._ignored_categories:
            return self._ignored_categories[guild_id]
        
        ignored = set()
        
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/tickets/bot/panels"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        panels = await resp.json()
                        for panel in panels:
                            cat_id = panel.get("category_id")
                            if cat_id:
                                ignored.add(int(cat_id))
        except Exception:
            pass
        
        self._ignored_categories[guild_id] = ignored
        return ignored
    
    def _is_ignored(self, channel: discord.abc.GuildChannel) -> bool:
        """Verifica se o canal está numa categoria de ticket"""
        if not hasattr(channel, 'category_id') or not channel.category_id:
            return False
        return channel.category_id in self._ignored_categories.get(channel.guild.id, set())
    
    async def _get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        """Busca canal de log configurado na API"""
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
    
    @staticmethod
    def _channel_type_name(channel: discord.abc.GuildChannel) -> str:
        type_map = {
            discord.ChannelType.text: "Texto",
            discord.ChannelType.voice: "Voz",
            discord.ChannelType.category: "Categoria",
            discord.ChannelType.stage_voice: "Palco",
            discord.ChannelType.forum: "Fórum",
            discord.ChannelType.news: "Anúncios",
        }
        return type_map.get(channel.type, str(channel.type))
    
    def _build_base_embed(self, title: str, color: discord.Color, channel: discord.abc.GuildChannel) -> discord.Embed:
        """Cria embed base para logs de canal"""
        embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
        embed.add_field(name="📛 Nome", value=channel.name, inline=True)
        embed.add_field(name="🆔 ID", value=channel.id, inline=True)
        embed.add_field(name="📋 Tipo", value=self._channel_type_name(channel), inline=True)
        
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="📁 Categoria", value=channel.category.name, inline=True)
        
        return embed
    
    def _build_log_data(self, channel: discord.abc.GuildChannel) -> dict:
        """Cria dados base para envio à API"""
        return {
            "channel_name": channel.name,
            "channel_id": str(channel.id),
            "channel_type": str(channel.type),
            "channel_type_name": self._channel_type_name(channel),
            "category_name": channel.category.name if hasattr(channel, 'category') and channel.category else None,
            "category_id": str(channel.category.id) if hasattr(channel, 'category') and channel.category else None,
            "position": channel.position
        }
    
    # ═══════════════ CACHE ═══════════════
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Atualiza cache de categorias ignoradas"""
        if not self.bot.is_ready():
            return
        for guild in self.bot.guilds:
            await self._get_ignored_categories(guild.id)
    
    # ═══════════════ CHANNEL CREATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if self._is_ignored(channel):
            return
        
        log_channel_id = await self._get_log_channel(channel.guild.id, "channel_create")
        
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_base_embed("📢 Canal criado", discord.Color.green(), channel)
                if isinstance(channel, discord.TextChannel) and channel.topic:
                    embed.add_field(name="📝 Tópico", value=channel.topic[:1024], inline=False)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=channel.guild.id,
            log_type="channel_create",
            channel_id=channel.id,
            data={**self._build_log_data(channel), "topic": channel.topic if isinstance(channel, discord.TextChannel) else None}
        )
    
    # ═══════════════ CHANNEL DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if self._is_ignored(channel):
            return
        
        log_channel_id = await self._get_log_channel(channel.guild.id, "channel_delete")
        
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_base_embed("🗑️ Canal deletado", discord.Color.red(), channel)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=channel.guild.id,
            log_type="channel_delete",
            channel_id=channel.id,
            data=self._build_log_data(channel)
        )
    
    # ═══════════════ CHANNEL UPDATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if self._is_ignored(after):
            return
        
        # Mudança só de posição → agrupa
        if before.position != after.position and before.name == after.name:
            guild_id = after.guild.id
            self._position_queue.setdefault(guild_id, {})[after.id] = (before.position, after.position, after.name)
            
            if guild_id in self._position_task:
                self._position_task[guild_id].cancel()
            self._position_task[guild_id] = asyncio.create_task(self._flush_position_changes(after.guild))
            return
        
        await self._log_single_channel_update(before, after)
    
    async def _flush_position_changes(self, guild: discord.Guild):
        await asyncio.sleep(1)
        
        queue = self._position_queue.pop(guild.id, {})
        if not queue:
            return
        
        log_channel_id = await self._get_log_channel(guild.id, "channel_update")
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes_list = [f"**{name}**: {old} → {new}" for _, (old, new, name) in queue.items()]
        
        embed = discord.Embed(
            title="🔢 Posições de canais atualizadas",
            description=f"{len(changes_list)} canal(is) reordenado(s)",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        chunk = ""
        for line in changes_list:
            if len(chunk) + len(line) > 1024:
                embed.add_field(name="📋 Mudanças", value=chunk, inline=False)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            embed.add_field(name="📋 Mudanças", value=chunk, inline=False)
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="channel_update",
            data={
                "type": "position_bulk",
                "changes": [
                    {"channel_id": str(cid), "channel_name": name, "old_position": old, "new_position": new}
                    for cid, (old, new, name) in queue.items()
                ]
            }
        )
    
    async def _log_single_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_channel_id = await self._get_log_channel(after.guild.id, "channel_update")
        if not log_channel_id:
            return
        
        log_channel = after.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes = {}
        
        if before.name != after.name:
            changes["name"] = {"old": before.name, "new": after.name}
        
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                changes["topic"] = {"old": before.topic, "new": after.topic}
            if before.slowmode_delay != after.slowmode_delay:
                changes["slowmode"] = {"old": before.slowmode_delay, "new": after.slowmode_delay}
            if before.nsfw != after.nsfw:
                changes["nsfw"] = {"old": before.nsfw, "new": after.nsfw}
        
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            if before.bitrate != after.bitrate:
                changes["bitrate"] = {"old": before.bitrate, "new": after.bitrate}
            if before.user_limit != after.user_limit:
                changes["user_limit"] = {"old": before.user_limit, "new": after.user_limit}
        
        old_cat = before.category.name if hasattr(before, 'category') and before.category else None
        new_cat = after.category.name if hasattr(after, 'category') and after.category else None
        if old_cat != new_cat:
            changes["category"] = {"old": old_cat, "new": new_cat}
        
        if {str(t.id): o for t, o in before.overwrites.items()} != {str(t.id): o for t, o in after.overwrites.items()}:
            changes["permissions"] = {"old": len(before.overwrites), "new": len(after.overwrites)}
        
        if not changes:
            return
        
        embed = discord.Embed(
            title="✏️ Canal editado",
            description=f"Canal {after.mention}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        name_map = {
            "name": "📛 Nome", "topic": "📝 Tópico", "slowmode": "⏱️ Slowmode",
            "nsfw": "🔞 NSFW", "bitrate": "🎵 Bitrate", "user_limit": "👥 Limite de usuários",
            "category": "📁 Categoria", "permissions": "🔒 Permissões"
        }
        
        for key, value in changes.items():
            embed.add_field(name=name_map.get(key, key), value=f"❌ {value['old']}\n✅ {value['new']}", inline=True)
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=after.guild.id,
            log_type="channel_update",
            channel_id=after.id,
            data={**self._build_log_data(after), "changes": changes}
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLogs(bot))