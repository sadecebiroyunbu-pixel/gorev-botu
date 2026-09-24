import os
import asyncpg
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                target TEXT,
                url TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                user_id BIGINT NOT NULL,
                task_id INTEGER NOT NULL,
                status TEXT DEFAULT 'bekliyor',
                photo_file_id TEXT,
                updated_at TEXT,
                PRIMARY KEY (user_id, task_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


# ---------- TASKS ----------

async def add_task(title, ttype, target, url):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO tasks (title, type, target, url, active, created_at) "
            "VALUES ($1, $2, $3, $4, 1, $5) RETURNING id",
            title, ttype, target, url, datetime.utcnow().isoformat()
        )
        return row["id"]


async def get_active_tasks():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM tasks WHERE active = 1 ORDER BY id")


async def get_all_tasks():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM tasks ORDER BY id")


async def get_task(task_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)


async def delete_task(task_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET active = 0 WHERE id = $1", task_id)


# ---------- PROGRESS ----------

async def get_progress(user_id, task_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM progress WHERE user_id = $1 AND task_id = $2", user_id, task_id
        )


async def set_progress(user_id, task_id, status, photo_file_id=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO progress (user_id, task_id, status, photo_file_id, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, task_id) DO UPDATE SET
                status = EXCLUDED.status,
                photo_file_id = EXCLUDED.photo_file_id,
                updated_at = EXCLUDED.updated_at
        """, user_id, task_id, status, photo_file_id, datetime.utcnow().isoformat())


async def get_user_progress_map(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT task_id, status FROM progress WHERE user_id = $1", user_id)
        return {r["task_id"]: r["status"] for r in rows}


async def all_tasks_approved(user_id):
    tasks = await get_active_tasks()
    if not tasks:
        return False
    prog = await get_user_progress_map(user_id)
    return all(prog.get(t["id"]) == "onaylandi" for t in tasks)


# ---------- SETTINGS (ödül linki) ----------

async def set_setting(key, value):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, value)


async def get_setting(key):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else None
