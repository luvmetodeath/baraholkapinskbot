import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import config
from database import posts as post_repo
from services.validators import validate_price
from services.post_service import build_post_text, build_contact_keyboard
from handlers.states import EditPrice

logger = logging.getLogger(__name__)
router = Router()

PRICE_COOLDOWN_MINUTES = 60  # раз в час


def _post_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"mypost:editprice:{post_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"mypost:delete:{post_id}"),
        ]
    ])


def _can_edit_price(post: dict) -> tuple[bool, int]:
    """Возвращает (можно_ли, минут_до_следующего)."""
    updated = post.get("price_updated_at")
    if not updated:
        return True, 0
    last = datetime.fromisoformat(updated)
    diff = (last + timedelta(minutes=PRICE_COOLDOWN_MINUTES)) - datetime.now()
    if diff.total_seconds() <= 0:
        return True, 0
    return False, int(diff.total_seconds() // 60) + 1


# ─────────────────────── /my ───────────────────────────────────

@router.message(Command("my"))
async def cmd_my_posts(message: Message, state: FSMContext):
    await state.clear()
    posts = await post_repo.get_user_posts(message.from_user.id)

    if not posts:
        await message.answer(
            "👤 <b>Ваш кабинет</b>\n\n"
            "У вас пока нет активных объявлений.\n\n"
            "Создать новое: /new",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"👤 <b>Ваш кабинет</b>\n\n"
        f"Активных объявлений: <b>{len(posts)}</b>",
        parse_mode="HTML",
    )

    for post in posts:
        date_str = post["created_at"][:10] if post["created_at"] else "—"
        can_edit, minutes_left = _can_edit_price(post)
        price_hint = "" if can_edit else f"\n<i>🕐 Цену можно изменить через {minutes_left} мин.</i>"

        text = (
            f"📦 <b>{post['title']}</b>\n"
            f"📝 {post['description']}\n"
            f"💰 {post['price']}\n"
            f"🗓 {date_str}\n"
            f"<code>#ID{post['id']}</code>"
            f"{price_hint}"
        )

        if post.get("photo_file_id"):
            await message.answer_photo(
                photo=post["photo_file_id"],
                caption=text,
                reply_markup=_post_keyboard(post["id"]),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                text,
                reply_markup=_post_keyboard(post["id"]),
                parse_mode="HTML",
            )


# ─────────────────────── Изменить цену ─────────────────────────

@router.callback_query(F.data.startswith("mypost:editprice:"))
async def my_post_editprice(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[2])
    post = await post_repo.get_post(post_id)

    if post is None:
        await callback.answer("❌ Объявление не найдено.", show_alert=True)
        return

    if post["user_id"] != callback.from_user.id:
        await callback.answer("⛔ Это не ваше объявление.", show_alert=True)
        return

    can_edit, minutes_left = _can_edit_price(post)
    if not can_edit:
        await callback.answer(
            f"⏳ Цену можно менять раз в час.\nПодождите ещё {minutes_left} мин.",
            show_alert=True,
        )
        return

    await state.set_state(EditPrice.waiting_price)
    await state.update_data(post_id=post_id)

    await callback.message.answer(
        f"✏️ Введи новую цену для объявления <b>«{post['title']}»</b>:\n\n"
        f"Текущая цена: <b>{post['price']}</b>\n\n"
        f"Отмена: /cancel",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditPrice.waiting_price)
async def process_new_price(message: Message, state: FSMContext, bot: Bot):
    ok, result = validate_price(message.text or "")
    if not ok:
        await message.answer(f"❌ {result}\n\nВведи цену ещё раз или /cancel:")
        return

    data = await state.get_data()
    post_id = data["post_id"]
    await state.clear()

    post = await post_repo.get_post(post_id)
    if post is None:
        await message.answer("❌ Объявление не найдено.")
        return

    old_price = post["price"]
    await post_repo.update_price(post_id, result)

    # Обновляем сообщение в канале
    if post.get("message_id"):
        try:
            new_text = build_post_text(post["title"], post["description"], result, post_id)
            keyboard = build_contact_keyboard(post["user_id"], post_id)

            if post.get("photo_file_id"):
                await bot.edit_message_caption(
                    chat_id=config.CHANNEL_ID,
                    message_id=post["message_id"],
                    caption=new_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await bot.edit_message_text(
                    chat_id=config.CHANNEL_ID,
                    message_id=post["message_id"],
                    text=new_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"Не удалось обновить пост в канале #{post_id}: {e}")

    await message.answer(
        f"✅ Цена обновлена!\n\n"
        f"Было: <b>{old_price}</b>\n"
        f"Стало: <b>{result}</b>\n\n"
        f"Объявление в канале обновлено.",
        parse_mode="HTML",
    )
    logger.info(f"Пользователь {message.from_user.id} изменил цену поста #{post_id}: {old_price} → {result}")


# ─────────────────────── Удалить ───────────────────────────────

@router.callback_query(F.data.startswith("mypost:delete:"))
async def my_post_delete(callback: CallbackQuery, bot: Bot):
    post_id = int(callback.data.split(":")[2])
    post = await post_repo.get_post(post_id)

    if post is None:
        await callback.answer("❌ Объявление не найдено.", show_alert=True)
        return

    if post["user_id"] != callback.from_user.id:
        await callback.answer("⛔ Это не ваше объявление.", show_alert=True)
        return

    if post.get("message_id"):
        try:
            await bot.delete_message(
                chat_id=config.CHANNEL_ID,
                message_id=post["message_id"],
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить из канала пост #{post_id}: {e}")

    await post_repo.delete_post(post_id)

    try:
        await callback.message.edit_caption(
            caption=f"🗑 <i>Объявление #ID{post_id} удалено.</i>",
            parse_mode="HTML",
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=f"🗑 <i>Объявление #ID{post_id} удалено.</i>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    logger.info(f"Пользователь {callback.from_user.id} удалил свой пост #{post_id}")
    await callback.answer("✅ Объявление удалено.")
