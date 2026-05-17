import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from src.core.config import config

class Stats(commands.Cog):
    """Envia estatísticas das guilds para a API"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.update_stats.start()
    
    def cog_unload(self):
        self.update_stats.cancel()
    
    # ═══════════════ HELPERS ═══════════════
    
    def _build_stats_embed(self, guild: discord.Guild, title: str) -> discord.Embed:
        """Cria embed de estatísticas"""
        embed = discord.Embed(title=title, description=f"Estatísticas de **{guild.name}** enviadas para API.", color=discord.Color.green())
        embed.add_field(name="👥 Membros", value=str(guild.member_count), inline=True)
        embed.add_field(name="📢 Canais", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="👔 Cargos", value=str(len(guild.roles)), inline=True)
        return embed
    
    def _count_online(self, guild: discord.Guild) -> int:
        """Conta membros online (não bots)"""
        return sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
    
    async def send_guild_stats(self, guild: discord.Guild):
        """Envia stats de uma guild para API"""
        try:
            payload = {
                "member_count": guild.member_count,
                "online_count": self._count_online(guild),
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles)
            }
            
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.put(f"{self.api_url}/guilds/{guild.id}/stats", json=payload) as resp:
                    if resp.status == 200:
                        print(f"📊 Stats enviadas: {guild.name} - {guild.member_count} membros")
                    else:
                        print(f"❌ Erro ao enviar stats de {guild.name}: {resp.status}")
        except aiohttp.ClientError as e:
            print(f"❌ Erro API stats {guild.name}: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado stats {guild.name}: {e}")
    
    # ═══════════════ LOOP ═══════════════
    
    @tasks.loop(minutes=15)
    async def update_stats(self):
        for guild in self.bot.guilds:
            await self.send_guild_stats(guild)
    
    @update_stats.before_loop
    async def before_update_stats(self):
        await self.bot.wait_until_ready()
    
    # ═══════════════ COMANDOS ═══════════════
    
    @app_commands.command(name="syncstats", description="Força sincronização de estatísticas")
    @app_commands.default_permissions(administrator=True)
    async def syncstats_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_guild_stats(interaction.guild)
        embed = self._build_stats_embed(interaction.guild, "📊 Stats sincronizadas")
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @commands.command(name="syncstats", description="Força sincronização de estatísticas")
    @commands.has_permissions(administrator=True)
    async def syncstats_prefix(self, ctx: commands.Context):
        async with ctx.typing():
            await self.send_guild_stats(ctx.guild)
            embed = self._build_stats_embed(ctx.guild, "📊 Stats sincronizadas")
            await ctx.send(embed=embed)
    
    # ═══════════════ EVENTOS ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.send_guild_stats(guild)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_guild_stats(member.guild)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.send_guild_stats(member.guild)

async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))