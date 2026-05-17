import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class EmojiLogs(commands.Cog):
    """Logs de eventos de emoji"""
    
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
    
    def _build_emoji_embed(self, title: str, description: str, color: discord.Color,
                           emoji: discord.Emoji, extra_fields: dict = None) -> discord.Embed:
        """Cria embed base para logs de emoji"""
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=emoji.url)
        embed.add_field(name="🆔 ID", value=emoji.id, inline=False)
        
        if extra_fields:
            for name, value in extra_fields.items():
                embed.add_field(name=name, value=value, inline=True)
        
        return embed
    
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        before_ids = {str(e.id): e for e in before}
        after_ids = {str(e.id): e for e in after}
        
        # Criados
        for emoji_id, emoji in after_ids.items():
            if emoji_id not in before_ids:
                await self._log_emoji_create(guild, emoji)
        
        # Deletados
        for emoji_id, emoji in before_ids.items():
            if emoji_id not in after_ids:
                await self._log_emoji_delete(guild, emoji)
        
        # Renomeados
        for emoji_id, emoji in after_ids.items():
            if emoji_id in before_ids:
                old_emoji = before_ids[emoji_id]
                if old_emoji.name != emoji.name:
                    await self._log_emoji_rename(guild, old_emoji, emoji)
    
    async def _log_emoji_create(self, guild: discord.Guild, emoji: discord.Emoji):
        log_channel_id = await self._get_log_channel(guild.id, "emoji_create")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_emoji_embed(
                    "😀 Emoji criado",
                    f"Emoji **:{emoji.name}:** adicionado ao servidor",
                    discord.Color.green(),
                    emoji,
                    {"📛 Nome": f":{emoji.name}:", "🎬 Animado": "Sim" if emoji.animated else "Não"}
                )
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=guild.id, log_type="emoji_create", data={
            "emoji_name": emoji.name, "emoji_id": str(emoji.id),
            "emoji_url": str(emoji.url), "animated": emoji.animated
        })
    
    async def _log_emoji_delete(self, guild: discord.Guild, emoji: discord.Emoji):
        log_channel_id = await self._get_log_channel(guild.id, "emoji_delete")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_emoji_embed(
                    "🗑️ Emoji deletado",
                    f"Emoji **:{emoji.name}:** removido do servidor",
                    discord.Color.red(),
                    emoji,
                    {"📛 Nome": f":{emoji.name}:"}
                )
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=guild.id, log_type="emoji_delete", data={
            "emoji_name": emoji.name, "emoji_id": str(emoji.id), "emoji_url": str(emoji.url)
        })
    
    async def _log_emoji_rename(self, guild: discord.Guild, old_emoji: discord.Emoji, new_emoji: discord.Emoji):
        log_channel_id = await self._get_log_channel(guild.id, "emoji_name_change")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_emoji_embed(
                    "✏️ Emoji renomeado",
                    "Emoji renomeado no servidor",
                    discord.Color.orange(),
                    new_emoji,
                    {"❌ Antes": f":{old_emoji.name}:", "✅ Depois": f":{new_emoji.name}:"}
                )
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=guild.id, log_type="emoji_name_change", data={
            "emoji_name": new_emoji.name, "emoji_id": str(new_emoji.id),
            "emoji_url": str(new_emoji.url), "old_name": old_emoji.name, "new_name": new_emoji.name
        })

async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiLogs(bot))