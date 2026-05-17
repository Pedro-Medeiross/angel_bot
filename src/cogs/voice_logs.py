import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class VoiceLogs(commands.Cog):
    """Detecta eventos de voz e pergunta pra API onde logar"""
    
    VOICE_ACTIONS = {
        (False, True): 'voice_join',
        (True, False): 'voice_leave',
        (True, True): 'voice_move',
    }
    
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
    
    def _create_voice_embed(self, member: discord.Member, action: str,
                            channel: discord.VoiceChannel,
                            old_channel: discord.VoiceChannel = None) -> discord.Embed:
        colors = {'voice_join': discord.Color.green(), 'voice_leave': discord.Color.red(), 'voice_move': discord.Color.orange()}
        
        titles = {
            'voice_join': ('🎤 Entrou em canal de voz', f'{member.mention} entrou em {channel.mention}'),
            'voice_leave': ('🔇 Saiu de canal de voz', f'{member.mention} saiu de {channel.mention}'),
            'voice_move': ('🔄 Trocou de canal de voz', f'{member.mention} moveu de {old_channel.mention} para {channel.mention}'),
        }
        
        title, description = titles.get(action, (action, ''))
        
        embed = discord.Embed(title=title, description=description, color=colors.get(action, discord.Color.blue()), timestamp=discord.utils.utcnow())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} | @{member.name}")
        return embed
    
    def _build_log_data(self, member: discord.Member, channel: discord.VoiceChannel, old_channel: discord.VoiceChannel = None) -> dict:
        return {
            "user_name": member.name,
            "display_name": member.display_name,
            "user_avatar": str(member.display_avatar.url),
            "channel_name": channel.name,
            "channel_id": str(channel.id),
            "members_in_channel": len(channel.members),
            "old_channel_name": old_channel.name if old_channel else None,
            "old_channel_id": str(old_channel.id) if old_channel else None,
        }
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                     before: discord.VoiceState,
                                     after: discord.VoiceState):
        if member.bot:
            return
        
        has_before = before.channel is not None
        has_after = after.channel is not None
        
        if has_before == has_after and (not has_before or before.channel == after.channel):
            return
        
        action = self.VOICE_ACTIONS.get((has_before, has_after))
        if not action:
            return
        
        channel = after.channel if has_after else before.channel
        old_channel = before.channel if action == 'voice_move' else None
        
        guild = member.guild
        log_channel_id = await self._get_log_channel(guild.id, action)
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._create_voice_embed(member, action, channel, old_channel)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id, log_type=action,
            user_id=member.id, channel_id=channel.id,
            data=self._build_log_data(member, channel, old_channel)
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceLogs(bot))