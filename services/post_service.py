import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from database import users as user_repo
from database import posts as post_repo

logger = logging.getLogger(__name__)


def build_post_text(title: str, description: str, price: str, post_id) -> str:
    return (
        f"📦 <b>Продам:</b> {title}\n"
        f"📝 {description}\n"
        f"💰 <b>Цена:</b> {price}\n\n"
        f"#ID{post_id}"
    )


def build_contact_keyboard(user_id: int, post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💬 Связаться",
            url=f"tg://user?id={user_id}",
        ),
    ]])


def build_moderation_keyboard(pending_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod:approve:{pending_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod:reject:{pending_id}"),
    ]])


def build_post_extend_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Актуально", callback_data=f"remind:keep:{post_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"remind:delete:{post_id}"),
    ]])


class PostService:

    @staticmethod
    async def check_cooldown(user_id: int) -> int:
        last_time = await user_repo.get_last_post_time(user_id)
        if last_time is None:
            return 0
        delta = timedelta(minutes=config.POST_COOLDOWN_MINUTES)
        diff = (last_time + delta) - datetime.now()
        if diff.total_seconds() <= 0:
            return 0
        return int(diff.total_seconds() // 60) + 1

    @staticmethod
    async def send_to_moderation(
        bot: Bot,
        user_id: int,
        username: str | None,
        title: str,
        description: str,
        price: str,
        photo_file_id: str | None = None,
    ) -> int:
        pending_id = await post_repo.create_pending(
            user_id, username, title, description, price, photo_file_id
        )

        contact = f"@{username}" if username else f"tg://user?id={user_id}"
        mod_text = (
            f"🔍 <b>Новое объявление на модерацию</b>\n"
            f"👤 {contact} (id: <code>{user_id}</code>)\n\n"
            + build_post_text(title, description, price, post_id=f"pending#{pending_id}")
        )
        keyboard = build_moderation_keyboard(pending_id)

        # Отправляем модераторам, если есть — иначе суперадминам
        from database import users as user_repo_local
        moderators = await user_repo_local.get_moderators()
        recipients = [m["user_id"] for m in moderators] if moderators else config.ADMIN_IDS

        for mod_id in recipients:
            try:
                if photo_file_id:
                    msg = await bot.send_photo(
                        chat_id=mod_id,
                        photo=photo_file_id,
                        caption=mod_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                else:
                    msg = await bot.send_message(
                        chat_id=mod_id,
                        text=mod_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                await post_repo.set_pending_admin_message(pending_id, msg.message_id)
            except Exception as e:
                logger.error(f"Не удалось отправить на модерацию {mod_id}: {e}")

        logger.info(f"Объявление отправлено на модерацию: pending_id={pending_id}")
        return pending_id

    @staticmethod
    async def publish_post(
        bot: Bot,
        user_id: int,
        username: str | None,
        title: str,
        description: str,
        price: str,
        photo_file_id: str | None = None,
    ) -> int:
        post_id = await post_repo.create_post(
            user_id, title, description, price, photo_file_id
        )

        text = build_post_text(title, description, price, post_id)
        keyboard = build_contact_keyboard(user_id, post_id)

        if photo_file_id:
            msg = await bot.send_photo(
                chat_id=config.CHANNEL_ID,
                photo=photo_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            msg = await bot.send_message(
                chat_id=config.CHANNEL_ID,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        await post_repo.set_message_id(post_id, msg.message_id)
        await user_repo.update_last_post_time(user_id)

        logger.info(
            f"Пост опубликован: post_id={post_id}, "
            f"user_id={user_id}, message_id={msg.message_id}"
        )
        return post_id
