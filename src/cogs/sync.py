import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from src.core.config import config

class Sync(commands.Cog):
    """Sincroniza guilds com a API"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
    
    @app_commands.command(name="sync", description="Sincroniza servidores com a API")
    @app_commands.default_permissions(administrator=True)
    async def sync_slash(self, interaction: discord.Interaction):
        """Comando slash /sync"""
        await self._do_sync(interaction)
    
    @commands.command(name="sync", description="Sincroniza servidores com a API")
    @commands.has_permissions(administrator=True)
    async def sync_prefix(self, ctx: commands.Context):
        """Comando prefix !sync"""
        await self._do_sync(ctx)
    
    async def _do_sync(self, context):
        """Executa a sincronização"""
        await context.defer(ephemeral=True)
        
        # Pega IDs de todas as guilds que o bot está
        guild_ids = [guild.id for guild in self.bot.guilds]
        
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(
                    f"{self.api_url}/sync",
                    json=guild_ids
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        embed = discord.Embed(
                            title="🔄 Sincronização concluída",
                            color=discord.Color.green()
                        )
                        embed.add_field(
                            name="✅ Criadas",
                            value=str(len(data["created"])),
                            inline=True
                        )
                        embed.add_field(
                            name="✔️ Já existiam",
                            value=str(len(data["existing"])),
                            inline=True
                        )
                        embed.add_field(
                            name="📊 Total",
                            value=str(data["total"]),
                            inline=True
                        )
                        
                        await context.send(embed=embed, ephemeral=True)
                    else:
                        await context.send(
                            f"❌ Erro na API: {response.status}",
                            ephemeral=True
                        )
        
        except aiohttp.ClientError as e:
            await context.send(
                f"❌ Erro ao comunicar com a API: {e}",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Sincroniza automaticamente quando o bot entra em um novo servidor"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(
                    f"{self.api_url}/sync",
                    json=[guild.id]
                ) as response:
                    if response.status == 200:
                        print(f"✅ Guild sincronizada ao entrar: {guild.name} ({guild.id})")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao sincronizar nova guild: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Sync(bot))