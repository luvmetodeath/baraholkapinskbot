import asyncio
import logging

from aiogram import Bot

import config
from database import posts as post_repo
from services.post_service import build_post_extend_keyboard

logger = logging.getLogger(__name__)

# Через сколько дней после публикации отправлять напоминание
REMINDER_AFTER_DAYS = config.REMINDER_DAYS


async def send_reminders(bot: Bot):
    """Проверяет посты и отправляет напоминания владельцам."""
    posts = await post_repo.get_posts_for_reminder(days=REMINDER_AFTER_DAYS)

    for post in posts:
        try:
            keyboard = build_post_extend_keyboard(post["id"])
            await bot.send_message(
                chat_id=post["user_id"],
                text=(
                    f"⏰ <b>Ваше объявление всё ещё актуально?</b>\n\n"
                    f"📦 <b>{post['title']}</b>\n"
                    f"💰 {post['price']}\n\n"
                    f"Оно было опубликовано {config.REMINDER_DAYS} дней назад.\n"
                    f"Выберите, что сделать с объявлением:"
                ),
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await post_repo.mark_reminder_sent(post["id"])
            logger.info(
                f"Напоминание отправлено: post_id={post['id']}, user_id={post['user_id']}"
            )
        except Exception as e:
            logger.error(
                f"Ошибка отправки напоминания post_id={post['id']}: {e}"
            )

    if posts:
        logger.info(f"Отправлено напоминаний: {len(posts)}")


async def reminder_loop(bot: Bot):
    """Фоновая задача — проверяет напоминания каждый час."""
    logger.info("Планировщик напоминаний запущен")
    while True:
        try:
            await send_reminders(bot)
        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
        await asyncio.sleep(3600)  # раз в час
