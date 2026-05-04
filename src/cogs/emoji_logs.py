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
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        """Detecta criação, deleção e mudança de nome de emojis"""
        
        before_ids = {str(e.id): e for e in before}
        after_ids = {str(e.id): e for e in after}
        
        # Emoji criado
        for emoji_id, emoji in after_ids.items():
            if emoji_id not in before_ids:
                log_channel_id = await self.get_log_channel(guild.id, "emoji_create")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="😀 Emoji criado",
                            description=f"Emoji **:{emoji.name}:** adicionado ao servidor",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_thumbnail(url=emoji.url)
                        embed.add_field(name="📛 Nome", value=f":{emoji.name}:", inline=True)
                        embed.add_field(name="🆔 ID", value=emoji.id, inline=True)
                        embed.add_field(name="🎬 Animado", value="Sim" if emoji.animated else "Não", inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="emoji_create",
                    data={
                        "emoji_name": emoji.name,
                        "emoji_id": str(emoji.id),
                        "emoji_url": str(emoji.url),
                        "animated": emoji.animated
                    }
                )
        
        # Emoji deletado
        for emoji_id, emoji in before_ids.items():
            if emoji_id not in after_ids:
                log_channel_id = await self.get_log_channel(guild.id, "emoji_delete")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🗑️ Emoji deletado",
                            description=f"Emoji **:{emoji.name}:** removido do servidor",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_thumbnail(url=emoji.url)
                        embed.add_field(name="📛 Nome", value=f":{emoji.name}:", inline=True)
                        embed.add_field(name="🆔 ID", value=emoji.id, inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=guild.id,
                    log_type="emoji_delete",
                    data={
                        "emoji_name": emoji.name,
                        "emoji_id": str(emoji.id),
                        "emoji_url": str(emoji.url)
                    }
                )
        
        # Emoji renomeado
        for emoji_id, emoji in after_ids.items():
            if emoji_id in before_ids:
                old_emoji = before_ids[emoji_id]
                if old_emoji.name != emoji.name:
                    log_channel_id = await self.get_log_channel(guild.id, "emoji_name_change")
                    
                    if log_channel_id:
                        log_channel = guild.get_channel(log_channel_id)
                        if log_channel:
                            embed = discord.Embed(
                                title="✏️ Emoji renomeado",
                                description=f"Emoji renomeado no servidor",
                                color=discord.Color.orange(),
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_thumbnail(url=emoji.url)
                            embed.add_field(name="❌ Antes", value=f":{old_emoji.name}:", inline=True)
                            embed.add_field(name="✅ Depois", value=f":{emoji.name}:", inline=True)
                            embed.add_field(name="🆔 ID", value=emoji.id, inline=False)
                            
                            await log_channel.send(embed=embed)
                    
                    await self.log_api.send_log(
                        guild_id=guild.id,
                        log_type="emoji_name_change",
                        data={
                            "emoji_name": emoji.name,
                            "emoji_id": str(emoji.id),
                            "emoji_url": str(emoji.url),
                            "old_name": old_emoji.name,
                            "new_name": emoji.name
                        }
                    )

async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiLogs(bot))