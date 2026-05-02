import discord
from discord.ext import commands, tasks
import aiohttp
from src.core.config import config

class Stats(commands.Cog):
    """Envia estatísticas das guilds para a API"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.update_stats.start()
    
    def cog_unload(self):
        self.update_stats.cancel()
    
    @tasks.loop(minutes=15)
    async def update_stats(self):
        """Atualiza stats de todas as guilds a cada 15 minutos"""
        for guild in self.bot.guilds:
            try:
                online_count = sum(
                    1 for member in guild.members
                    if member.status != discord.Status.offline and not member.bot
                )
                
                payload = {
                    "member_count": guild.member_count,
                    "online_count": online_count,
                    "channel_count": len(guild.channels),
                    "role_count": len(guild.roles)
                }
                
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    async with session.put(
                        f"{self.api_url}/guilds/{guild.id}/stats",
                        json=payload
                    ) as response:
                        if response.status == 200:
                            print(f"📊 Stats enviadas: {guild.name} - {guild.member_count} membros")
                        else:
                            print(f"❌ Erro ao enviar stats de {guild.name}: {response.status}")
            
            except aiohttp.ClientError as e:
                print(f"❌ Erro API stats {guild.name}: {e}")
            except Exception as e:
                print(f"❌ Erro inesperado stats {guild.name}: {e}")
    
    @update_stats.before_loop
    async def before_update_stats(self):
        """Espera o bot ficar pronto antes de começar"""
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Envia stats iniciais quando entra em um novo servidor"""
        await self.send_guild_stats(guild)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Atualiza stats quando um membro entra"""
        await self.send_guild_stats(member.guild)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Atualiza stats quando um membro sai"""
        await self.send_guild_stats(member.guild)
    
    async def send_guild_stats(self, guild: discord.Guild):
        """Envia stats de uma guild específica"""
        try:
            online_count = sum(
                1 for member in guild.members
                if member.status != discord.Status.offline and not member.bot
            )
            
            payload = {
                "member_count": guild.member_count,
                "online_count": online_count,
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles)
            }
            
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.put(
                    f"{self.api_url}/guilds/{guild.id}/stats",
                    json=payload
                ) as response:
                    if response.status == 200:
                        print(f"📊 Stats atualizadas: {guild.name}")
        except Exception as e:
            print(f"❌ Erro stats {guild.name}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))