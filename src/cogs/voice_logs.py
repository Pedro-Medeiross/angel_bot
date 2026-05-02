import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class VoiceLogs(commands.Cog):
    """Detecta eventos de voz e pergunta pra API onde logar"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.log_api = log_api
    
    async def get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        """Pergunta pra API qual canal usar para esse tipo de log"""
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
    
    def create_voice_embed(self, member: discord.Member, action: str,
                           channel: discord.VoiceChannel,
                           old_channel: discord.VoiceChannel = None) -> discord.Embed:
        """Cria embed formatado para logs de voz"""
        
        colors = {
            'voice_join': discord.Color.green(),
            'voice_leave': discord.Color.red(),
            'voice_move': discord.Color.orange(),
        }
        
        if action == 'voice_join':
            title = '🎤 Entrou em canal de voz'
            description = f'{member.mention} entrou em {channel.mention}'
        elif action == 'voice_leave':
            title = '🔇 Saiu de canal de voz'
            description = f'{member.mention} saiu de {channel.mention}'
        elif action == 'voice_move':
            title = '🔄 Trocou de canal de voz'
            description = f'{member.mention} moveu de {old_channel.mention} para {channel.mention}'
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=colors.get(action, discord.Color.blue()),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        
        return embed
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState,
                                     after: discord.VoiceState):
        """Detecta mudança de voz e loga no canal configurado"""
        
        if member.bot:
            return
        
        guild = member.guild
        
        # Determina ação
        if before.channel is None and after.channel is not None:
            action = 'voice_join'
            channel = after.channel
            old_channel = None
        elif before.channel is not None and after.channel is None:
            action = 'voice_leave'
            channel = before.channel
            old_channel = None
        elif before.channel and after.channel and before.channel != after.channel:
            action = 'voice_move'
            channel = after.channel
            old_channel = before.channel
        else:
            return
        
        # 1️⃣ Busca canal de log do Discord
        log_channel_id = await self.get_log_channel(guild.id, action)
        
        # 2️⃣ Envia embed pro Discord (se tiver canal)
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = self.create_voice_embed(
                    member=member,
                    action=action,
                    channel=channel,
                    old_channel=old_channel
                )
                await log_channel.send(embed=embed)
        
        # 3️⃣ Envia log pra API (dashboard/WebSocket)
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type=action,
            user_id=member.id,
            channel_id=channel.id,
            data={
                "user_name": str(member),
                "user_avatar": str(member.display_avatar.url),
                "channel_name": channel.name,
                "channel_id": str(channel.id),
                "members_in_channel": len(channel.members),
                "old_channel_name": old_channel.name if old_channel else None,
                "old_channel_id": str(old_channel.id) if old_channel else None
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceLogs(bot))