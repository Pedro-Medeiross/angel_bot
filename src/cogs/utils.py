import discord
from discord.ext import commands
from discord import app_commands

class Utils(commands.Cog):
    """Comandos utilitários"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _build_ping_embed(self, latency_ms: int) -> discord.Embed:
        return discord.Embed(
            title="🏓 Pong!",
            description=f"Latência: **{latency_ms}ms**",
            color=discord.Color.green()
        )
    
    @app_commands.command(name="ping", description="Mostra a latência do bot")
    async def ping_slash(self, interaction: discord.Interaction):
        embed = self._build_ping_embed(round(self.bot.latency * 1000))
        await interaction.response.send_message(embed=embed)
    
    @commands.command(name="ping", description="Mostra a latência do bot")
    async def ping_prefix(self, ctx: commands.Context):
        embed = self._build_ping_embed(round(self.bot.latency * 1000))
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))