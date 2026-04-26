import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TOKEN = os.getenv('DISCORD_TOKEN')
    PREFIX = os.getenv('PREFIX', '!a')
    GUILD_IDS = [int(id.strip()) for id in os.getenv('GUILD_IDS', '').split(',') if id.strip()]
    API_URL = os.getenv('API_URL')
    API_USER = os.getenv('API_USER')
    API_PASS = os.getenv('API_PASS')
    
    
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN não encontrado no arquivo .env")

config = Config()