import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from handlers.states import PostForm
from services.validators import validate_title, validate_description, validate_price
from services.post_service import PostService, build_post_text, build_post_extend_keyboard
from database import users as user_repo

logger = logging.getLogger(__name__)

router = Router()

# ─────────────────────────── /start ────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await user_repo.get_or_create_user(user.id, user.username)

    await message.answer(
        "👋 Привет! Я бот для публикации объявлений на барахолке.\n\n"
        "Нажми /new чтобы создать объявление."
    )


# ─────────────────────────── /new ──────────────────────────────

@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext):
    user = message.from_user
    await user_repo.get_or_create_user(user.id, user.username)

    if await user_repo.is_banned(user.id):
        await message.answer("🚫 Вы заблокированы и не можете публиковать объявления.")
        logger.warning(f"Забаненный пользователь попытался создать пост: {user.id}")
        return

    await state.clear()
    await state.set_state(PostForm.title)
    await message.answer("📦 Что продаёшь? (до 60 символов)")


# ─────────────────────── Шаг 1: Название ───────────────────────

@router.message(PostForm.title)
async def step_title(message: Message, state: FSMContext):
    ok, result = validate_title(message.text or "")
    if not ok:
        await message.answer(f"❌ {result}\n\nПопробуй ещё раз:")
        return

    await state.update_data(title=result)
    await state.set_state(PostForm.description)
    await message.answer("📝 Добавь описание (до 180 символов):")


# ─────────────────────── Шаг 2: Описание ───────────────────────

@router.message(PostForm.description)
async def step_description(message: Message, state: FSMContext):
    ok, result = validate_description(message.text or "")
    if not ok:
        await message.answer(f"❌ {result}\n\nПопробуй ещё раз:")
        return

    await state.update_data(description=result)
    await state.set_state(PostForm.price)
    await message.answer("💰 Какая цена? (например: 500, 1500 ₽, договорная)")


# ─────────────────────── Шаг 3: Цена ───────────────────────────

@router.message(PostForm.price)
async def step_price(message: Message, state: FSMContext):
    ok, result = validate_price(message.text or "")
    if not ok:
        await message.answer(f"❌ {result}\n\nВведи цену ещё раз:")
        return

    await state.update_data(price=result)
    await state.set_state(PostForm.photo)
    await message.answer(
        "📸 Отправь фото товара.\n\n"
        "Если фото нет — напиши /skip"
    )


# ─────────────────────── Шаг 4: Фото ───────────────────────────

@router.message(PostForm.photo, F.photo)
async def step_photo(message: Message, state: FSMContext):
    # Берём фото в максимальном качестве
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await show_preview(message, state)


@router.message(PostForm.photo, Command("skip"))
async def step_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await show_preview(message, state)


@router.message(PostForm.photo)
async def step_photo_wrong(message: Message):
    await message.answer("📸 Отправь фото товара или напиши /skip чтобы пропустить.")


# ─────────────────────── Предпросмотр ──────────────────────────

async def show_preview(message: Message, state: FSMContext):
    await state.set_state(PostForm.preview)
    data = await state.get_data()

    preview_text = (
        "👀 <b>Предпросмотр объявления:</b>\n\n"
        + build_post_text(
            data["title"], data["description"], data["price"], post_id="XXXX"
        )
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="post:confirm"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="post:edit"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="post:cancel"),
        ],
    ])

    photo_id = data.get("photo_file_id")
    if photo_id:
        await message.answer_photo(
            photo=photo_id,
            caption=preview_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await message.answer(preview_text, reply_markup=keyboard, parse_mode="HTML")


# ─────────────────────── Подтверждение ─────────────────────────

@router.callback_query(PostForm.preview, F.data == "post:confirm")
async def confirm_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = callback.from_user
    await callback.message.edit_reply_markup(reply_markup=None)

    # Проверка бана
    if await user_repo.is_banned(user.id):
        await callback.message.answer("🚫 Вы заблокированы.")
        await state.clear()
        await callback.answer()
        return

    # Проверка cooldown
    wait_minutes = await PostService.check_cooldown(user.id)
    if wait_minutes > 0:
        await callback.message.answer(
            f"⏱ Вы сможете опубликовать следующее объявление через "
            f"{wait_minutes} мин."
        )
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()
    await state.clear()

    try:
        pending_id = await PostService.send_to_moderation(
            bot=bot,
            user_id=user.id,
            username=user.username,
            title=data["title"],
            description=data["description"],
            price=data["price"],
            photo_file_id=data.get("photo_file_id"),
        )
        await user_repo.update_last_post_time(user.id)
        await callback.message.answer(
            "⏳ Ваше объявление отправлено на проверку модератору.\n"
            "После одобрения оно появится в канале.",
        )
        logger.info(f"Пост отправлен на модерацию: pending_id={pending_id}, user_id={user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки на модерацию user_id={user.id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка. Попробуй позже."
        )

    await callback.answer()


# ─────────────────────── Изменить ──────────────────────────────

@router.callback_query(PostForm.preview, F.data == "post:edit")
async def edit_post(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await state.set_state(PostForm.title)
    await callback.message.answer(
        "✏️ Начинаем заново.\n\n📦 Что продаёшь? (до 60 символов)"
    )
    await callback.answer()


# ─────────────────────── Отмена ────────────────────────────────

@router.callback_query(PostForm.preview, F.data == "post:cancel")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer("❌ Объявление отменено.")
    logger.info(f"Пользователь {callback.from_user.id} отменил создание поста")
    await callback.answer()


# ─────────────────── /cancel в любой момент ────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия для отмены.")
        return
    await state.clear()
    await message.answer("❌ Действие отменено.")
