import discord
from discord.ext import commands
import aiohttp
from src.core.config import config

class TicketNotifications(commands.Cog):
    """Notificações de tickets abertos em canal de log"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
    
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
    
    @commands.Cog.listener()
    async def on_ticket_created(self, guild: discord.Guild, event):
        """Notifica criação de ticket no canal de log configurado"""
        log_channel_id = await self._get_log_channel(guild.id, "ticket_create")
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        user = guild.get_member(int(event.user_id)) or await self.bot.fetch_user(int(event.user_id))
        channel = guild.get_channel(int(event.channel_id))
        
        # Busca prioridade da API
        priority = "medium"
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild.id}/tickets/bot/{event.ticket_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        priority = data.get("priority", "medium")
        except:
            pass
        
        priority_colors = {
            "urgent": discord.Color.red(),
            "high": discord.Color.orange(),
            "medium": discord.Color.blue(),
            "low": discord.Color.green(),
        }
        priority_emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        
        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"Um novo ticket foi criado por {user.mention}",
            color=priority_colors.get(priority, discord.Color.blue()),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id} | @{user.name}")
        
        embed.add_field(name="📝 Ticket ID", value=event.ticket_id, inline=True)
        embed.add_field(name="👤 Usuário", value=user.mention, inline=True)
        embed.add_field(name="⚠️ Prioridade", value=f"{priority_emoji.get(priority, '🟡')} {priority.upper()}", inline=True)
        
        if channel:
            embed.add_field(name="📢 Canal", value=channel.mention, inline=True)
        
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketNotifications(bot))