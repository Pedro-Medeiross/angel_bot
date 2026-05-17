import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord
    TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    PREFIX: str = os.getenv('PREFIX', '!a')
    GUILD_IDS: list[int] = [int(id.strip()) for id in os.getenv('GUILD_IDS', '').split(',') if id.strip()]
    
    # API
    API_URL: str = os.getenv('API_URL', '')
    API_USER: str = os.getenv('API_USER', '')
    API_PASS: str = os.getenv('API_PASS', '')
    
    # Bot Server
    BOT_PORT: int = int(os.getenv('BOT_PORT', '8002'))
    
    # Debug
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Validação
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN não encontrado no arquivo .env")

config = Config()