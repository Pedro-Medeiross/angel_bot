import discord
from discord.ext import commands
from .config import config
import logging

logger = logging.getLogger(__name__)

class MyBot(commands.Bot):
    """Bot principal com carregamento de cogs e comandos slash"""
    
    COGS = [
        'cogs.utils',
        'cogs.voice_logs',
        'cogs.sync',
        'cogs.stats',
        'cogs.message_logs',
        'cogs.server_logs',
        'cogs.emoji_logs',
        'cogs.invite_logs',
        'cogs.channel_logs',
        'cogs.role_logs',
        'cogs.member_events',
        'cogs.tickets',
        'cogs.ticket_notifications',
    ]
    
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=config.PREFIX, intents=intents)
    
    async def setup_hook(self):
        """Carrega cogs, sincroniza comandos e inicia servidor de eventos"""
        await self._load_cogs()
        await self._sync_commands()
        self._start_event_server()
    
    async def _load_cogs(self):
        """Carrega todas as cogs configuradas"""
        for cog in self.COGS:
            try:
                await self.load_extension(f'src.{cog}')
                logger.info(f'✅ Cog carregada: {cog}')
            except Exception as e:
                logger.error(f'❌ Erro ao carregar {cog}: {e}')
    
    async def _sync_commands(self):
        """Sincroniza comandos slash com guilds de debug"""
        if config.GUILD_IDS:
            for guild_id in config.GUILD_IDS:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            logger.info(f'🔄 Comandos slash sincronizados para: {config.GUILD_IDS}')
    
    def _start_event_server(self):
        """Inicia servidor FastAPI para eventos"""
        from src.api.server import start_api_server
        start_api_server(self)
        logger.info("🌐 Servidor de eventos iniciado")
    
    async def on_ready(self):
        logger.info(f'✅ Bot conectado como {self.user}')
        logger.info(f'📊 Latência: {round(self.latency * 1000)}ms')
        logger.info(f'🔧 Prefixo: {config.PREFIX}')
