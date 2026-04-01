import logging
from datetime import datetime

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import config
from database import users as user_repo
from database import posts as post_repo

logger = logging.getLogger(__name__)

router = Router()


async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    return await user_repo.is_dynamic_admin(user_id)


async def is_superadmin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("adminhelp"))
async def cmd_adminhelp(message: Message):
    if not await is_admin(message.from_user.id):
        return
    extra = ""
    if await is_superadmin(message.from_user.id):
        extra = (
            "\n<b>Суперадмин:</b>\n"
            "/addadmin @username — добавить администратора\n"
            "/removeadmin @username — убрать администратора\n"
            "/admins — список всех администраторов\n"
            "/addmod @username — назначить модератора\n"
            "/removemod @username — снять модератора\n"
            "/mods — список модераторов\n"
        )
    await message.answer(
        "👮 <b>Команды администратора:</b>\n\n"
        "/ban @username — постоянный бан\n"
        "/tempban @username 60 — бан на N минут\n"
        "/unban @username — разблокировать\n"
        "/delete {post_id} — удалить пост из канала\n"
        "/adminhelp — эта справка"
        + extra,
        parse_mode="HTML",
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /ban @username")
        return
    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден в базе.")
        return
    if await is_admin(user["user_id"]):
        await message.answer("❌ Нельзя забанить администратора.")
        return
    await user_repo.ban_user(user["user_id"])
    logger.info(f"Админ {message.from_user.id} навсегда забанил {user['user_id']}")
    await message.answer(f"🚫 Пользователь {target} заблокирован навсегда.")
    try:
        await bot.send_message(chat_id=user["user_id"], text="🚫 Вы заблокированы в боте навсегда.")
    except Exception:
        pass


@router.message(Command("tempban"))
async def cmd_tempban(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[2].strip().isdigit():
        await message.answer("Использование: /tempban @username {минуты}\nПример: /tempban @user 60")
        return
    target = parts[1].strip()
    minutes = int(parts[2].strip())
    if minutes <= 0:
        await message.answer("❌ Укажи количество минут больше 0.")
        return
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден в базе.")
        return
    if await is_admin(user["user_id"]):
        await message.answer("❌ Нельзя забанить администратора.")
        return
    ban_until = await user_repo.tempban_user(user["user_id"], minutes)
    ban_until_str = datetime.fromisoformat(ban_until).strftime("%d.%m.%Y %H:%M")
    logger.info(f"Админ {message.from_user.id} временно забанил {user['user_id']} на {minutes} мин")
    await message.answer(
        f"⏳ Пользователь {target} заблокирован на <b>{minutes} мин.</b>\n"
        f"Бан истекает: {ban_until_str}",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            chat_id=user["user_id"],
            text=f"⏳ Вы временно заблокированы в боте.\nБан истекает: {ban_until_str}",
        )
    except Exception:
        pass


@router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /unban @username")
        return
    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден.")
        return
    await user_repo.unban_user(user["user_id"])
    logger.info(f"Админ {message.from_user.id} разбанил {user['user_id']}")
    await message.answer(f"✅ Пользователь {target} разблокирован.")
    try:
        await bot.send_message(
            chat_id=user["user_id"],
            text="✅ Ваша блокировка снята. Можете снова публиковать объявления.",
        )
    except Exception:
        pass


@router.message(Command("delete"))
async def cmd_delete(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /delete {post_id}")
        return
    post_id = int(parts[1].strip())
    post = await post_repo.get_post(post_id)
    if post is None:
        await message.answer(f"❌ Пост #ID{post_id} не найден.")
        return
    if post["message_id"]:
        try:
            await bot.delete_message(chat_id=config.CHANNEL_ID, message_id=post["message_id"])
        except Exception as e:
            logger.warning(f"Не удалось удалить из канала: {e}")
    await post_repo.delete_post(post_id)
    logger.info(f"Админ {message.from_user.id} удалил пост #ID{post_id}")
    await message.answer(f"✅ Пост #ID{post_id} удалён.")
    try:
        await bot.send_message(
            chat_id=post["user_id"],
            text=f"❌ Ваше объявление <b>«{post['title']}»</b> (#ID{post_id}) удалено модератором.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message, bot: Bot):
    if not await is_superadmin(message.from_user.id):
        await message.answer("⛔ Только суперадмин может добавлять администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /addadmin @username")
        return
    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден.\nОн должен хотя бы раз написать боту.")
        return
    if user["user_id"] in config.ADMIN_IDS:
        await message.answer(f"ℹ️ {target} уже является суперадмином.")
        return
    await user_repo.add_admin(user["user_id"], user.get("username"), message.from_user.id)
    logger.info(f"Суперадмин {message.from_user.id} добавил админа {user['user_id']}")
    await message.answer(f"✅ {target} назначен администратором.")
    try:
        await bot.send_message(
            chat_id=user["user_id"],
            text="👮 Вы назначены администратором бота барахолки.\n\nКоманды: /adminhelp",
        )
    except Exception:
        pass


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message, bot: Bot):
    if not await is_superadmin(message.from_user.id):
        await message.answer("⛔ Только суперадмин может убирать администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /removeadmin @username")
        return
    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден.")
        return
    if user["user_id"] in config.ADMIN_IDS:
        await message.answer("❌ Нельзя убрать суперадмина из config.py через эту команду.")
        return
    await user_repo.remove_admin(user["user_id"])
    logger.info(f"Суперадмин {message.from_user.id} убрал админа {user['user_id']}")
    await message.answer(f"✅ {target} лишён прав администратора.")
    try:
        await bot.send_message(chat_id=user["user_id"], text="ℹ️ Ваши права администратора сняты.")
    except Exception:
        pass


@router.message(Command("admins"))
async def cmd_admins(message: Message):
    if not await is_superadmin(message.from_user.id):
        return
    dynamic = await user_repo.get_dynamic_admins()
    lines = ["👮 <b>Администраторы бота:</b>\n", "<b>Суперадмины (config.py):</b>"]
    for uid in config.ADMIN_IDS:
        lines.append(f"  • <code>{uid}</code>")
    if dynamic:
        lines.append("\n<b>Добавленные через бота:</b>")
        for a in dynamic:
            uname = f"@{a['username']}" if a["username"] else f"id:{a['user_id']}"
            added = a["added_at"][:10] if a["added_at"] else "?"
            lines.append(f"  • {uname} (добавлен {added})")
    else:
        lines.append("\n<i>Дополнительных администраторов нет.</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─────────────────────── /stats ────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return

    from database import posts as post_repo
    stats = await post_repo.get_stats()

    top_lines = ""
    for i, seller in enumerate(stats["top_sellers"], 1):
        top_lines += f"  {i}. id:<code>{seller['user_id']}</code> — {seller['cnt']} объявл.\n"

    await message.answer(
        "📊 <b>Статистика барахолки</b>\n\n"
        f"📦 Всего объявлений: <b>{stats['total_posts']}</b>\n"
        f"📅 За сегодня: <b>{stats['today_posts']}</b>\n"
        f"📆 За 7 дней: <b>{stats['week_posts']}</b>\n"
        f"⏳ На модерации: <b>{stats['pending_count']}</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"🚫 Забанено: <b>{stats['banned_users']}</b>\n\n"
        + (f"🏆 <b>Топ продавцов:</b>\n{top_lines}" if top_lines else ""),
        parse_mode="HTML",
    )


# ─────────────────────── /addmod ───────────────────────────────

@router.message(Command("addmod"))
async def cmd_addmod(message: Message, bot: Bot):
    if not await is_superadmin(message.from_user.id):
        await message.answer("⛔ Только суперадмин может назначать модераторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /addmod @username")
        return

    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден.\nОн должен хотя бы раз написать боту.")
        return

    await user_repo.add_moderator(user["user_id"], user.get("username"), message.from_user.id)
    logger.info(f"Суперадмин {message.from_user.id} назначил модератора {user['user_id']}")
    await message.answer(f"✅ {target} назначен модератором.\nТеперь посты на проверку будут приходить ему.")

    try:
        await bot.send_message(
            chat_id=user["user_id"],
            text=(
                "👁 Вы назначены модератором барахолки.\n\n"
                "Все новые объявления будут приходить вам на проверку.\n"
                "Вы можете одобрять или отклонять их прямо в этом чате."
            ),
        )
    except Exception:
        pass


# ─────────────────────── /removemod ────────────────────────────

@router.message(Command("removemod"))
async def cmd_removemod(message: Message, bot: Bot):
    if not await is_superadmin(message.from_user.id):
        await message.answer("⛔ Только суперадмин может убирать модераторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /removemod @username")
        return

    target = parts[1].strip()
    user = await user_repo.find_user_by_username(target)
    if user is None:
        await message.answer(f"❌ Пользователь {target} не найден.")
        return

    await user_repo.remove_moderator(user["user_id"])
    logger.info(f"Суперадмин {message.from_user.id} снял модератора {user['user_id']}")
    await message.answer(f"✅ {target} снят с должности модератора.")

    try:
        await bot.send_message(
            chat_id=user["user_id"],
            text="ℹ️ Ваши права модератора барахолки были сняты.",
        )
    except Exception:
        pass


# ─────────────────────── /mods ─────────────────────────────────

@router.message(Command("mods"))
async def cmd_mods(message: Message):
    if not await is_superadmin(message.from_user.id):
        return

    moderators = await user_repo.get_moderators()

    if not moderators:
        await message.answer(
            "👁 <b>Модераторы</b>\n\n"
            "Модераторов пока нет.\n"
            "Пока они не назначены — посты приходят суперадминам.\n\n"
            "Назначить: /addmod @username",
            parse_mode="HTML",
        )
        return

    lines = ["👁 <b>Модераторы барахолки:</b>\n"]
    for m in moderators:
        uname = f"@{m['username']}" if m["username"] else f"id:{m['user_id']}"
        added = m["added_at"][:10] if m["added_at"] else "?"
        lines.append(f"  • {uname} (с {added})")

    lines.append(f"\nВсего: <b>{len(moderators)}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")
