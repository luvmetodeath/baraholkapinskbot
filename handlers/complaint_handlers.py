import logging
import re

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import config
from database import users as user_repo

logger = logging.getLogger(__name__)
router = Router()


def _ban_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚫 Забанить навсегда",
            callback_data=f"cban:perm:{target_user_id}",
        ),
        InlineKeyboardButton(
            text="⏳ Бан на 24ч",
            callback_data=f"cban:temp:{target_user_id}",
        ),
        InlineKeyboardButton(
            text="✅ Не банить",
            callback_data=f"cban:skip:{target_user_id}",
        ),
    ]])


# ─────────────────────── /жалоба ───────────────────────────────
# Формат: /жалоба @username причина
# Также поддерживается /complaint для удобства

@router.message(Command("жалоба", "complaint", "report"))
async def cmd_complaint(message: Message, bot: Bot):
    user = message.from_user

    # Регистрируем пользователя если нет
    await user_repo.get_or_create_user(user.id, user.username)

    # Парсим: /жалоба @username текст причины
    text = message.text or ""
    # Убираем саму команду
    body = re.sub(r"^/\S+\s*", "", text).strip()

    # Ищем @username в начале
    match = re.match(r"(@\w+)\s*(.*)", body, re.DOTALL)
    if not match:
        await message.answer(
            "❌ Неверный формат.\n\n"
            "Используй: <code>/жалоба @username причина</code>\n"
            "Пример: <code>/жалоба @vasya продаёт подделки</code>",
            parse_mode="HTML",
        )
        return

    target_username = match.group(1)
    reason = match.group(2).strip()

    if not reason:
        await message.answer(
            "❌ Укажи причину жалобы.\n\n"
            "Пример: <code>/жалоба @vasya продаёт подделки</code>",
            parse_mode="HTML",
        )
        return

    if len(reason) > 300:
        reason = reason[:300] + "..."

    # Ищем цель в БД
    target = await user_repo.find_user_by_username(target_username)
    if target is None:
        await message.answer(
            f"❌ Пользователь {target_username} не найден.\n"
            "Он должен хотя бы раз написать боту."
        )
        return

    # Нельзя жаловаться на себя
    if target["user_id"] == user.id:
        await message.answer("❌ Нельзя жаловаться на самого себя.")
        return

    # Нельзя жаловаться на админа
    if await user_repo.is_dynamic_admin(target["user_id"]) or target["user_id"] in config.ADMIN_IDS:
        await message.answer("❌ Нельзя жаловаться на администратора.")
        return

    # Формируем сообщение для всех админов
    from_contact = f"@{user.username}" if user.username else f"id:<code>{user.id}</code>"
    target_contact = f"@{target['username']}" if target.get("username") else f"id:<code>{target['user_id']}</code>"

    admin_text = (
        f"🚩 <b>Новая жалоба</b>\n\n"
        f"👤 От: {from_contact}\n"
        f"🎯 На: {target_contact}\n\n"
        f"📄 <b>Причина:</b>\n{reason}"
    )

    keyboard = _ban_keyboard(target["user_id"])
    sent = False

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            sent = True
        except Exception as e:
            logger.error(f"Не удалось отправить жалобу админу {admin_id}: {e}")

    # Пробуем также динамических админов
    dynamic_admins = await user_repo.get_dynamic_admins()
    for a in dynamic_admins:
        if a["user_id"] in config.ADMIN_IDS:
            continue  # уже отправили выше
        try:
            await bot.send_message(
                chat_id=a["user_id"],
                text=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            sent = True
        except Exception as e:
            logger.error(f"Не удалось отправить жалобу динамическому админу {a['user_id']}: {e}")

    if sent:
        await message.answer(
            "✅ Жалоба отправлена модераторам. Они рассмотрят её в ближайшее время."
        )
        logger.info(
            f"Жалоба от {user.id} на {target['user_id']} ({target_username}): {reason[:50]}"
        )
    else:
        await message.answer("❌ Не удалось отправить жалобу. Попробуй позже.")


# ─────────────── Кнопки решения по жалобе ──────────────────────

@router.callback_query(F.data.startswith("cban:perm:"))
async def cban_permanent(callback: CallbackQuery, bot: Bot):
    if not (callback.from_user.id in config.ADMIN_IDS
            or await user_repo.is_dynamic_admin(callback.from_user.id)):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    target_id = int(callback.data.split(":")[2])
    target_user = await user_repo.get_or_create_user(target_id)

    await user_repo.ban_user(target_id)

    uname = f"@{target_user.get('username')}" if target_user.get("username") else f"id:{target_id}"
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"🚫 Пользователь {uname} заблокирован навсегда.")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="🚫 Вы заблокированы в боте навсегда по жалобе.",
        )
    except Exception:
        pass

    logger.info(f"Админ {callback.from_user.id} навсегда забанил {target_id} по жалобе")
    await callback.answer()


@router.callback_query(F.data.startswith("cban:temp:"))
async def cban_temp(callback: CallbackQuery, bot: Bot):
    if not (callback.from_user.id in config.ADMIN_IDS
            or await user_repo.is_dynamic_admin(callback.from_user.id)):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    target_id = int(callback.data.split(":")[2])
    target_user = await user_repo.get_or_create_user(target_id)

    ban_until = await user_repo.tempban_user(target_id, minutes=60 * 24)  # 24 часа
    from datetime import datetime
    ban_str = datetime.fromisoformat(ban_until).strftime("%d.%m.%Y %H:%M")

    uname = f"@{target_user.get('username')}" if target_user.get("username") else f"id:{target_id}"
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"⏳ Пользователь {uname} заблокирован на 24 часа (до {ban_str}).")

    try:
        await bot.send_message(
            chat_id=target_id,
            text=f"⏳ Вы временно заблокированы на 24 часа по жалобе.\nБан истекает: {ban_str}",
        )
    except Exception:
        pass

    logger.info(f"Админ {callback.from_user.id} временно забанил {target_id} на 24ч по жалобе")
    await callback.answer()


@router.callback_query(F.data.startswith("cban:skip:"))
async def cban_skip(callback: CallbackQuery):
    if not (callback.from_user.id in config.ADMIN_IDS
            or await user_repo.is_dynamic_admin(callback.from_user.id)):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    target_id = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ Жалоба на id:{target_id} отклонена, пользователь не забанен.")
    logger.info(f"Админ {callback.from_user.id} отклонил жалобу на {target_id}")
    await callback.answer()
