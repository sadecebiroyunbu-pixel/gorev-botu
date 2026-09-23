import os
import aiosqlite
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "gorevbot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT NOT NULL,          -- 'kanal' veya 'bot'
                target TEXT,                 -- kanal: @kullaniciadi ya da -100... chat_id
                url TEXT NOT NULL,           -- kullanıcıya açılacak link
                active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                status TEXT DEFAULT 'bekliyor',   -- bekliyor / inceleniyor / onaylandi / reddedildi
                photo_file_id TEXT,
                updated_at TEXT,
                PRIMARY KEY (user_id, task_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()


# ---------- TASKS ----------

async def add_task(title, ttype, target, url):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tasks (title, type, target, url, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (title, ttype, target, url, datetime.utcnow().isoformat())
        )
        await db.commit()
        return cur.lastrowid


async def get_active_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tasks WHERE active = 1 ORDER BY id")
        return await cur.fetchall()


async def get_all_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tasks ORDER BY id")
        return await cur.fetchall()


async def get_task(task_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return await cur.fetchone()


async def delete_task(task_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task_id,))
        await db.commit()


# ---------- PROGRESS ----------

async def get_progress(user_id, task_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM progress WHERE user_id = ? AND task_id = ?", (user_id, task_id)
        )
        return await cur.fetchone()


async def set_progress(user_id, task_id, status, photo_file_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO progress (user_id, task_id, status, photo_file_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, task_id) DO UPDATE SET
                status=excluded.status,
                photo_file_id=excluded.photo_file_id,
                updated_at=excluded.updated_at
        """, (user_id, task_id, status, photo_file_id, datetime.utcnow().isoformat()))
        await db.commit()


async def get_user_progress_map(user_id):
    """{task_id: status} döner"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT task_id, status FROM progress WHERE user_id = ?", (user_id,))
        rows = await cur.fetchall()
        return {r["task_id"]: r["status"] for r in rows}


async def all_tasks_approved(user_id):
    tasks = await get_active_tasks()
    if not tasks:
        return False
    prog = await get_user_progress_map(user_id)
    return all(prog.get(t["id"]) == "onaylandi" for t in tasks)


# ---------- SETTINGS (ödül linki) ----------

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        await db.commit()


async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None
