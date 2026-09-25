# database.py

import aiosqlite
from datetime import datetime

DB_NAME = "prgram.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                referrer INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                task_type TEXT,
                title TEXT,
                link TEXT,
                chat_id TEXT,
                reward INTEGER,
                budget INTEGER DEFAULT 0,
                remaining INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                join_date TIMESTAMP,
                revoked INTEGER DEFAULT 0,
                UNIQUE(user_id, task_id)
            )
        """)
        
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(user_id: int, username: str, full_name: str, referrer: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, referrer, balance) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, full_name, referrer, 0)
        )
        await db.commit()

async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_balance(user_id: int):
    user = await get_user(user_id)
    return user[3] if user else 0

async def create_task(owner_id: int, task_type: str, title: str, link: str, chat_id: str, reward: int, budget: int):
    remaining = budget // reward if reward > 0 else 0
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO tasks 
               (owner_id, task_type, title, link, chat_id, reward, budget, remaining) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (owner_id, task_type, title, link, chat_id, reward, budget, remaining)
        )
        await db.commit()
        return cursor.lastrowid

async def get_active_tasks(task_type: str = None, user_id: int = None, limit: int = 15):
    async with aiosqlite.connect(DB_NAME) as db:
        if task_type and user_id:
            query = """
                SELECT t.* FROM tasks t
                WHERE t.status = 'active' 
                  AND t.task_type = ? 
                  AND t.remaining > 0
                  AND t.id NOT IN (
                      SELECT task_id FROM completions 
                      WHERE user_id = ? AND revoked = 0
                  )
                ORDER BY t.id DESC LIMIT ?
            """
            async with db.execute(query, (task_type, user_id, limit)) as cursor:
                return await cursor.fetchall()
        elif task_type:
            query = """
                SELECT * FROM tasks 
                WHERE status = 'active' AND task_type = ? AND remaining > 0 
                ORDER BY id DESC LIMIT ?
            """
            async with db.execute(query, (task_type, limit)) as cursor:
                return await cursor.fetchall()
        else:
            query = """
                SELECT * FROM tasks 
                WHERE status = 'active' AND remaining > 0 
                ORDER BY id DESC LIMIT ?
            """
            async with db.execute(query, (limit,)) as cursor:
                return await cursor.fetchall()

async def get_task(task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            return await cursor.fetchone()

async def add_completion(user_id: int, task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO completions (user_id, task_id, join_date) VALUES (?, ?, ?)",
                (user_id, task_id, datetime.now())
            )
            await db.execute(
                "UPDATE tasks SET remaining = remaining - 1 WHERE id = ? AND remaining > 0",
                (task_id,)
            )
            await db.execute(
                "UPDATE tasks SET status = 'finished' WHERE id = ? AND remaining <= 0",
                (task_id,)
            )
            await db.commit()
            return True
        except:
            return False

async def check_completion(user_id: int, task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM completions WHERE user_id = ? AND task_id = ? AND revoked = 0",
            (user_id, task_id)
        ) as cursor:
            return await cursor.fetchone()
