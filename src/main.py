import asyncio
import sys
from core.bot import MyBot
from core.config import config

async def main():
    bot = MyBot()
    async with bot:
        await bot.start(config.TOKEN)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())