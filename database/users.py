import logging
from datetime import datetime, timedelta

from database.db import get_db

logger = logging.getLogger(__name__)


async def get_or_create_user(user_id: int, username: str | None = None):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username),
            )
            await db.commit()
            logger.info(f"Новый пользователь создан: {user_id} (@{username})")
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()

        return dict(row)


async def is_banned(user_id: int) -> bool:
    """Проверяет бан — постоянный или временный."""
    async with get_db() as db:
        async with db.execute(
            "SELECT is_banned, ban_until FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return False
    if row["is_banned"] == 1:
        ban_until = row["ban_until"]
        if ban_until is None:
            return True  # постоянный бан
        # Временный бан — проверяем истёк ли
        if datetime.fromisoformat(ban_until) > datetime.now():
            return True
        # Бан истёк — снимаем автоматически
        await unban_user(user_id)
    return False


async def get_ban_info(user_id: int) -> dict | None:
    """Возвращает информацию о бане или None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT is_banned, ban_until FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row or not row["is_banned"]:
        return None
    return {"is_banned": row["is_banned"], "ban_until": row["ban_until"]}


async def ban_user(user_id: int):
    """Постоянный бан."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_banned = 1, ban_until = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
    logger.info(f"Пользователь забанен навсегда: {user_id}")


async def tempban_user(user_id: int, minutes: int):
    """Временный бан на N минут."""
    until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_banned = 1, ban_until = ? WHERE user_id = ?",
            (until, user_id),
        )
        await db.commit()
    logger.info(f"Пользователь забанен на {minutes} мин: {user_id}")
    return until


async def unban_user(user_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_banned = 0, ban_until = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
    logger.info(f"Пользователь разбанен: {user_id}")


async def get_last_post_time(user_id: int) -> datetime | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT last_post_time FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row and row["last_post_time"]:
        return datetime.fromisoformat(row["last_post_time"])
    return None


async def update_last_post_time(user_id: int):
    now = datetime.now().isoformat()
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET last_post_time = ? WHERE user_id = ?",
            (now, user_id),
        )
        await db.commit()


async def find_user_by_username(username: str) -> dict | None:
    clean = username.lstrip("@")
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM users WHERE username = ?", (clean,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


# ─────────────── Динамические администраторы ───────────────────

async def add_admin(user_id: int, username: str | None, added_by: int):
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO admins (user_id, username, added_by) VALUES (?, ?, ?)",
            (user_id, username, added_by),
        )
        await db.commit()
    logger.info(f"Добавлен администратор: {user_id} (@{username}), добавил: {added_by}")


async def remove_admin(user_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
    logger.info(f"Удалён администратор: {user_id}")


async def get_dynamic_admins() -> list[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM admins") as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def is_dynamic_admin(user_id: int) -> bool:
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id FROM admins WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row is not None



# ─────────────── Модераторы ─────────────────────────────────────

async def add_moderator(user_id: int, username: str | None, added_by: int):
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO moderators (user_id, username, added_by) VALUES (?, ?, ?)",
            (user_id, username, added_by),
        )
        await db.commit()
    logger.info(f"Добавлен модератор: {user_id} (@{username}), добавил: {added_by}")


async def remove_moderator(user_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM moderators WHERE user_id = ?", (user_id,))
        await db.commit()
    logger.info(f"Удалён модератор: {user_id}")


async def get_moderators() -> list[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM moderators") as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def is_moderator(user_id: int) -> bool:
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id FROM moderators WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row is not None
