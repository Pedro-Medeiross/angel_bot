import discord
from discord.ext import commands
from discord import app_commands

class Utils(commands.Cog):
    """Comandos utilitários"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # Comando Slash (/)
    @app_commands.command(name="ping", description="Mostra a latência do bot")
    async def ping_slash(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latência: **{latency}ms**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    # Comando Prefix (!)
    @commands.command(name="ping", description="Mostra a latência do bot")
    async def ping_prefix(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latência: **{latency}ms**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utils(bot))