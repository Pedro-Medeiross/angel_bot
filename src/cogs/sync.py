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
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
    
    # ═══════════════ HELPERS ═══════════════
    
    async def _sync_guilds(self, guild_ids: list[int]) -> dict | None:
        """Envia IDs das guilds para API e retorna resposta"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(f"{self.api_url}/guilds/sync", json=guild_ids) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao sincronizar: {e}")
        return None
    
    def _build_sync_embed(self, data: dict) -> discord.Embed:
        """Cria embed com resultado da sincronização"""
        embed = discord.Embed(title="🔄 Sincronização concluída", color=discord.Color.green())
        embed.add_field(name="✅ Criadas", value=str(len(data["created"])), inline=True)
        embed.add_field(name="✔️ Já existiam", value=str(len(data["existing"])), inline=True)
        embed.add_field(name="📊 Total", value=str(data["total"]), inline=True)
        return embed
    
    # ═══════════════ COMANDOS ═══════════════
    
    @app_commands.command(name="sync", description="Sincroniza servidores com a API")
    @app_commands.default_permissions(administrator=True)
    async def sync_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild_ids = [g.id for g in self.bot.guilds]
        data = await self._sync_guilds(guild_ids)
        
        if data:
            embed = self._build_sync_embed(data)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Erro ao comunicar com a API.", ephemeral=True)
    
    @commands.command(name="sync", description="Sincroniza servidores com a API")
    @commands.has_permissions(administrator=True)
    async def sync_prefix(self, ctx: commands.Context):
        async with ctx.typing():
            guild_ids = [g.id for g in self.bot.guilds]
            data = await self._sync_guilds(guild_ids)
            
            if data:
                embed = self._build_sync_embed(data)
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Erro ao comunicar com a API.")
    
    # ═══════════════ EVENTOS ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        data = await self._sync_guilds([guild.id])
        if data:
            print(f"✅ Guild sincronizada: {guild.name} ({guild.id})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Sync(bot))