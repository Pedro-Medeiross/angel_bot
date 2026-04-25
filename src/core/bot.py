import discord
from discord.ext import commands
from .config import config

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix=config.PREFIX,
            intents=intents
        )
    
    async def setup_hook(self):
        """Carrega todas as cogs"""
        cogs = [
            'cogs.utils',
        ]
        
        for cog in cogs:
            await self.load_extension(f'src.{cog}')
            print(f'✅ Cog carregada: {cog}')
    
    async def on_ready(self):
        await self.tree.sync()
        print(f'✅ Bot conectado como {self.user}')
        print(f'📊 Latência: {round(self.latency * 1000)}ms')
        print(f'🔧 Prefixo: {config.PREFIX}')