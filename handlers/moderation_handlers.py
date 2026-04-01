import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from database import posts as post_repo
from services.post_service import PostService
from handlers.states import RejectReason

logger = logging.getLogger(__name__)
router = Router()


async def _is_admin(user_id: int) -> bool:
    from database import users as user_repo
    if user_id in config.ADMIN_IDS:
        return True
    return await user_repo.is_dynamic_admin(user_id)


async def _can_moderate(user_id: int) -> bool:
    """Модерировать могут: суперадмины, динамические админы и модераторы."""
    from database import users as user_repo
    if user_id in config.ADMIN_IDS:
        return True
    if await user_repo.is_dynamic_admin(user_id):
        return True
    return await user_repo.is_moderator(user_id)


# ─────────────────────── Одобрить ──────────────────────────────

@router.callback_query(F.data.startswith("mod:approve:"))
async def approve_post(callback: CallbackQuery, bot: Bot):
    if not await _can_moderate(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    pending_id = int(callback.data.split(":")[2])
    pending = await post_repo.get_pending(pending_id)

    if pending is None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("❌ Объявление уже обработано.", show_alert=True)
        return

    try:
        post_id = await PostService.publish_post(
            bot=bot,
            user_id=pending["user_id"],
            username=pending["username"],
            title=pending["title"],
            description=pending["description"],
            price=pending["price"],
            photo_file_id=pending["photo_file_id"],
        )

        try:
            await bot.send_message(
                chat_id=pending["user_id"],
                text=f"✅ Ваше объявление <b>«{pending['title']}»</b> одобрено и опубликовано! (#ID{post_id})",
                parse_mode="HTML",
            )
        except Exception:
            pass

        await post_repo.delete_pending(pending_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"✅ Объявление #ID{post_id} опубликовано.")
        logger.info(f"Админ {callback.from_user.id} одобрил pending_id={pending_id} → post_id={post_id}")

    except Exception as e:
        logger.error(f"Ошибка публикации при одобрении pending_id={pending_id}: {e}")
        await callback.answer("❌ Ошибка публикации.", show_alert=True)

    await callback.answer()


# ─────────────────────── Отклонить — шаг 1 ─────────────────────

@router.callback_query(F.data.startswith("mod:reject:"))
async def reject_post_ask_reason(callback: CallbackQuery, state: FSMContext):
    if not await _can_moderate(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    pending_id = int(callback.data.split(":")[2])
    pending = await post_repo.get_pending(pending_id)

    if pending is None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("❌ Объявление уже обработано.", show_alert=True)
        return

    await state.set_state(RejectReason.waiting_reason)
    await state.update_data(pending_id=pending_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✏️ Укажи причину отклонения объявления <b>«{pending['title']}»</b>\n\n"
        f"Она будет отправлена пользователю.\n"
        f"Или напиши /skipreason чтобы отклонить без причины.",
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────── Отклонить — шаг 2 ─────────────────────

@router.message(RejectReason.waiting_reason)
async def reject_post_with_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pending_id = data["pending_id"]
    reason = message.text.strip() if message.text else ""
    await _do_reject(message, state, bot, pending_id, reason)


@router.message(RejectReason.waiting_reason, Command("skipreason"))
async def reject_post_no_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pending_id = data["pending_id"]
    await _do_reject(message, state, bot, pending_id, reason=None)


async def _do_reject(message: Message, state: FSMContext, bot: Bot, pending_id: int, reason: str | None):
    await state.clear()

    pending = await post_repo.get_pending(pending_id)
    if pending is None:
        await message.answer("❌ Объявление не найдено — возможно уже обработано.")
        return

    # Уведомляем продавца
    if reason:
        user_text = (
            f"❌ Ваше объявление <b>«{pending['title']}»</b> отклонено.\n\n"
            f"📄 <b>Причина:</b> {reason}"
        )
    else:
        user_text = f"❌ Ваше объявление <b>«{pending['title']}»</b> отклонено модератором."

    try:
        await bot.send_message(
            chat_id=pending["user_id"],
            text=user_text,
            parse_mode="HTML",
        )
    except Exception:
        pass

    await post_repo.delete_pending(pending_id)

    reason_display = f"\nПричина: {reason}" if reason else ""
    await message.answer(f"🗑 Объявление отклонено.{reason_display}")
    logger.info(f"Админ {message.from_user.id} отклонил pending_id={pending_id}, причина: {reason}")
