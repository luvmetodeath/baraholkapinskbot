import logging
from datetime import datetime, timedelta

from database.db import get_db

logger = logging.getLogger(__name__)


async def create_post(
    user_id: int, title: str, description: str,
    price: str, photo_file_id: str | None = None
) -> int:
    """Создаёт запись поста со статусом 'published' и возвращает его ID."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO posts (user_id, title, description, price, photo_file_id, status)
               VALUES (?, ?, ?, ?, ?, 'published')""",
            (user_id, title, description, price, photo_file_id),
        )
        await db.commit()
        post_id = cursor.lastrowid
    logger.info(f"Пост создан в БД: id={post_id}, user_id={user_id}")
    return post_id


async def set_message_id(post_id: int, message_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE posts SET message_id = ? WHERE id = ?",
            (message_id, post_id),
        )
        await db.commit()


async def get_post(post_id: int) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM posts WHERE id = ?", (post_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_post(post_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        await db.commit()
    logger.info(f"Пост удалён из БД: id={post_id}")


# ─────────────── Pending (модерация) ───────────────────────────

async def create_pending(
    user_id: int, username: str | None,
    title: str, description: str,
    price: str, photo_file_id: str | None = None,
) -> int:
    """Создаёт черновик, ожидающий одобрения админа."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO pending_posts
               (user_id, username, title, description, price, photo_file_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, title, description, price, photo_file_id),
        )
        await db.commit()
        pending_id = cursor.lastrowid
    logger.info(f"Черновик на модерацию: id={pending_id}, user_id={user_id}")
    return pending_id


async def set_pending_admin_message(pending_id: int, admin_message_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE pending_posts SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, pending_id),
        )
        await db.commit()


async def get_pending(pending_id: int) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM pending_posts WHERE id = ?", (pending_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_pending(pending_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM pending_posts WHERE id = ?", (pending_id,))
        await db.commit()


# ─────────────── Напоминания ────────────────────────────────────

async def get_posts_for_reminder(days: int) -> list[dict]:
    """Возвращает опубликованные посты старше N дней, которым ещё не отправляли напоминание."""
    threshold = (datetime.now() - timedelta(days=days)).isoformat()
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM posts
               WHERE status = 'published'
                 AND reminder_sent = 0
                 AND created_at <= ?""",
            (threshold,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def mark_reminder_sent(post_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE posts SET reminder_sent = 1 WHERE id = ?", (post_id,)
        )
        await db.commit()


async def reset_reminder(post_id: int):
    """Сбрасывает флаг напоминания — следующее придёт снова через N дней."""
    async with get_db() as db:
        await db.execute(
            "UPDATE posts SET reminder_sent = 0, created_at = datetime('now') WHERE id = ?",
            (post_id,),
        )
        await db.commit()


# ─────────────── Жалобы ────────────────────────────────────────

async def add_complaint(post_id: int, user_id: int) -> bool:
    """Добавляет жалобу. Возвращает True если новая, False если уже жаловался."""
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO complaints (post_id, user_id) VALUES (?, ?)",
                (post_id, user_id),
            )
            await db.commit()
        return True
    except Exception:
        return False  # UNIQUE constraint — уже жаловался


async def get_complaint_count(post_id: int) -> int:
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM complaints WHERE post_id = ?", (post_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def get_user_posts(user_id: int) -> list[dict]:
    """Возвращает все активные посты пользователя."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM posts WHERE user_id = ? AND status = 'published' ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_price(post_id: int, new_price: str):
    """Обновляет цену поста и время последнего изменения цены."""
    async with get_db() as db:
        await db.execute(
            "UPDATE posts SET price = ?, price_updated_at = datetime('now') WHERE id = ?",
            (new_price, post_id),
        )
        await db.commit()
    logger.info(f"Цена поста #{post_id} обновлена: {new_price}")


async def get_stats() -> dict:
    """Возвращает статистику для /stats."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM posts WHERE status = 'published'"
        ) as c:
            total_posts = (await c.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM posts WHERE status = 'published' AND created_at >= date('now')"
        ) as c:
            today_posts = (await c.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM posts WHERE status = 'published' AND created_at >= date('now', '-7 days')"
        ) as c:
            week_posts = (await c.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM users"
        ) as c:
            total_users = (await c.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE is_banned = 1"
        ) as c:
            banned_users = (await c.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM pending_posts"
        ) as c:
            pending_count = (await c.fetchone())["cnt"]

        async with db.execute(
            """SELECT user_id, COUNT(*) as cnt FROM posts
               WHERE status = 'published'
               GROUP BY user_id ORDER BY cnt DESC LIMIT 5"""
        ) as c:
            top_sellers = await c.fetchall()

    return {
        "total_posts": total_posts,
        "today_posts": today_posts,
        "week_posts": week_posts,
        "total_users": total_users,
        "banned_users": banned_users,
        "pending_count": pending_count,
        "top_sellers": [dict(r) for r in top_sellers],
    }



