import asyncio
import sys
import os

# Adiciona o diretório pai ao path do Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.bot import MyBot
from src.core.config import config

async def main():
    bot = MyBot()
    async with bot:
        await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(main())