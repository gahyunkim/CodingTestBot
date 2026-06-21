import os

import aiosqlite

DB_PATH = "/data/bot.db" if os.path.isdir("/data") else "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                discord_id      TEXT PRIMARY KEY,
                github_username TEXT NOT NULL,
                discord_name    TEXT,
                author_name     TEXT
            )
        """)
        # 기존 DB에 author_name 컬럼이 없으면 추가
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN author_name TEXT")
        except Exception:
            pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_repos (
                discord_id TEXT NOT NULL,
                repo       TEXT NOT NULL,
                PRIMARY KEY (discord_id, repo)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                amount     INTEGER NOT NULL,
                reason     TEXT,
                date       TEXT NOT NULL,
                paid       INTEGER DEFAULT 0
            )
        """)
        await conn.commit()


async def register_user(discord_id: str, github_username: str, discord_name: str, author_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            INSERT INTO users (discord_id, github_username, discord_name, author_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                github_username = excluded.github_username,
                discord_name    = excluded.discord_name,
                author_name     = CASE WHEN excluded.author_name != '' THEN excluded.author_name ELSE author_name END
        """, (discord_id, github_username, discord_name, author_name))
        await conn.commit()


async def update_author_name(discord_id: str, author_name: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE users SET author_name = ? WHERE discord_id = ?",
            (author_name, discord_id)
        )
        await conn.commit()


async def get_user_by_discord(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT discord_id, github_username, discord_name, author_name FROM users WHERE discord_id = ?",
            (discord_id,)
        ) as cur:
            return await cur.fetchone()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT discord_id, github_username, discord_name, author_name FROM users"
        ) as cur:
            return await cur.fetchall()


async def add_fine(discord_id: str, amount: int, reason: str, date: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO fines (discord_id, amount, reason, date) VALUES (?, ?, ?, ?)",
            (discord_id, amount, reason, date)
        )
        await conn.commit()


async def get_total_fine(discord_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM fines WHERE discord_id = ? AND paid = 0",
            (discord_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_all_fines_summary():
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("""
            SELECT u.discord_id, u.discord_name, u.github_username,
                   COALESCE(SUM(CASE WHEN f.paid = 0 THEN f.amount ELSE 0 END), 0) AS unpaid
            FROM users u
            LEFT JOIN fines f ON u.discord_id = f.discord_id
            GROUP BY u.discord_id
            ORDER BY unpaid DESC
        """) as cur:
            return await cur.fetchall()


async def add_repo(discord_id: str, repo: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO user_repos (discord_id, repo) VALUES (?, ?)",
            (discord_id, repo)
        )
        await conn.commit()


async def remove_repo(discord_id: str, repo: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM user_repos WHERE discord_id = ? AND repo = ?",
            (discord_id, repo)
        )
        await conn.commit()


async def get_repos(discord_id: str) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT repo FROM user_repos WHERE discord_id = ?",
            (discord_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def pay_fines(discord_id: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE fines SET paid = 1 WHERE discord_id = ? AND paid = 0",
            (discord_id,)
        )
        await conn.commit()
