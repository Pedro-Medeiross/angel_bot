import discord
from discord.ext import commands
from .config import config

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        
        super().__init__(
            command_prefix=config.PREFIX,
            intents=intents
        )
    
    async def setup_hook(self):
        """Carrega todas as cogs"""
        cogs = [
            'cogs.utils',
            'cogs.voice_logs',
            'cogs.sync',
        ]
        
        for cog in cogs:
            await self.load_extension(f'src.{cog}')
            print(f'✅ Cog carregada: {cog}')
        
        # Sincroniza comandos slash para guilds específicas
        if config.GUILD_IDS:
            for guild_id in config.GUILD_IDS:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            print(f'🔄 Comandos slash sincronizados para: {config.GUILD_IDS}')
    
    async def on_ready(self):
        print(f'✅ Bot conectado como {self.user}')
        print(f'📊 Latência: {round(self.latency * 1000)}ms')
        print(f'🔧 Prefixo: {config.PREFIX}')