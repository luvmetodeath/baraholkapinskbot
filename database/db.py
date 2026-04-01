import aiosqlite
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

DB_PATH = "flea_market.db"


async def init_db():
    """Создаёт таблицы, если они ещё не существуют."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                last_post_time  TEXT,
                is_banned       INTEGER NOT NULL DEFAULT 0,
                ban_until       TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL,
                price           TEXT NOT NULL,
                photo_file_id   TEXT,
                message_id      INTEGER,
                status          TEXT NOT NULL DEFAULT 'published',
                reminder_sent   INTEGER NOT NULL DEFAULT 0,
                price_updated_at TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_posts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                username        TEXT,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL,
                price           TEXT NOT NULL,
                photo_file_id   TEXT,
                admin_message_id INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        # Динамические администраторы (добавляются через бота)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                added_by    INTEGER,
                added_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        # Модераторы — получают посты на проверку
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderators (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                added_by    INTEGER,
                added_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        # Жалобы на посты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(post_id, user_id)
            )
        """)
        await db.commit()
    logger.info("Таблицы БД готовы")


@asynccontextmanager
async def get_db():
    """Контекстный менеджер для работы с БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
