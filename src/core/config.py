import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TOKEN = os.getenv('DISCORD_TOKEN')
    PREFIX = os.getenv('PREFIX', '!')
    
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN não encontrado no arquivo .env")

config = Config()