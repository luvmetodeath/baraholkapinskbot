import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from handlers import user_router, admin_router, moderation_router, reminder_router, complaint_router, my_posts_router
from services.reminder_service import reminder_loop

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    logger.info("Запуск бота...")

    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(moderation_router)
    dp.include_router(reminder_router)
    dp.include_router(complaint_router)
    dp.include_router(my_posts_router)
    dp.include_router(user_router)

    # Запускаем планировщик напоминаний фоном
    asyncio.create_task(reminder_loop(bot))

    logger.info("Бот запущен и слушает обновления")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
