import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

import config
from database import posts as post_repo

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("remind:keep:"))
async def reminder_keep(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[2])
    post = await post_repo.get_post(post_id)

    if post is None or post["user_id"] != callback.from_user.id:
        await callback.answer("❌ Объявление не найдено.", show_alert=True)
        return

    # Сбрасываем флаг, чтобы напоминание пришло снова через N дней
    await post_repo.reset_reminder(post_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Отлично! Объявление остаётся активным.")
    logger.info(f"Пользователь {callback.from_user.id} продлил пост #{post_id}")
    await callback.answer()


@router.callback_query(F.data.startswith("remind:delete:"))
async def reminder_delete(callback: CallbackQuery, bot: Bot):
    post_id = int(callback.data.split(":")[2])
    post = await post_repo.get_post(post_id)

    if post is None or post["user_id"] != callback.from_user.id:
        await callback.answer("❌ Объявление не найдено.", show_alert=True)
        return

    # Удаляем из канала
    if post["message_id"]:
        try:
            await bot.delete_message(
                chat_id=config.CHANNEL_ID,
                message_id=post["message_id"],
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение из канала: {e}")

    await post_repo.delete_post(post_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🗑 Объявление удалено из канала.")
    logger.info(f"Пользователь {callback.from_user.id} удалил пост #{post_id} через напоминание")
    await callback.answer()
