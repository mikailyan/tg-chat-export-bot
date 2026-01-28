import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_settings, Settings
from app.handlers import router

logging.basicConfig(level=logging.INFO)

async def main():
    settings = load_settings()
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp["settings"] = settings
    dp.include_router(router)

    await dp.start_polling(bot, settings=settings)

if __name__ == "__main__":
    asyncio.run(main())
