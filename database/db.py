"""
database/db.py — Base de datos SQLite para Choppa Security v6
"""
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "security.db")


async def init_db():
    """Inicializa la base de datos"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS warns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                moderator_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                anti_raid INTEGER DEFAULT 1,
                anti_spam INTEGER DEFAULT 1,
                auto_mod INTEGER DEFAULT 1,
                anti_phishing INTEGER DEFAULT 1,
                logs_enabled INTEGER DEFAULT 1,
                log_channel_id INTEGER,
                raid_threshold INTEGER DEFAULT 5,
                spam_threshold INTEGER DEFAULT 5,
                mute_duration INTEGER DEFAULT 600,
                warn_kick INTEGER DEFAULT 3,
                warn_ban INTEGER DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


# ═══════════════════════════════════════════
#  WARNS
# ═══════════════════════════════════════════

async def add_warn(guild_id, user_id, moderator_id, reason):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason)
        )
        await db.commit()


async def get_warns(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id)
        )
        return await cursor.fetchall()


async def get_warn_count(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM warns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def clear_warns(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM warns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()


# ═══════════════════════════════════════════
#  LOGS
# ═══════════════════════════════════════════

async def add_log(guild_id, event_type, user_id=None, moderator_id=None, details=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO security_logs (guild_id, event_type, user_id, moderator_id, details) VALUES (?, ?, ?, ?, ?)",
            (guild_id, event_type, user_id, moderator_id, details)
        )
        await db.commit()


async def get_logs(guild_id, limit=25, event_type=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if event_type:
            cursor = await db.execute(
                "SELECT * FROM security_logs WHERE guild_id = ? AND event_type = ? ORDER BY created_at DESC LIMIT ?",
                (guild_id, event_type, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM security_logs WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
                (guild_id, limit)
            )
        return await cursor.fetchall()


# ═══════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════

async def get_settings(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "guild_id": row[0],
                "anti_raid": bool(row[1]),
                "anti_spam": bool(row[2]),
                "auto_mod": bool(row[3]),
                "anti_phishing": bool(row[4]),
                "logs_enabled": bool(row[5]),
                "log_channel_id": row[6],
                "raid_threshold": row[7],
                "spam_threshold": row[8],
                "mute_duration": row[9],
                "warn_kick": row[10],
                "warn_ban": row[11],
            }
        return None


async def ensure_settings(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT guild_id FROM guild_settings WHERE guild_id = ?", (guild_id,))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
            await db.commit()


async def update_settings(guild_id, **kwargs):
    await ensure_settings(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in kwargs.items():
            await db.execute(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        await db.commit()


# ═══════════════════════════════════════════
#  BLACKLIST / WHITELIST
# ═══════════════════════════════════════════

async def add_blacklist(guild_id, user_id, reason):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO blacklist (guild_id, user_id, reason) VALUES (?, ?, ?)", (guild_id, user_id, reason))
        await db.commit()


async def remove_blacklist(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blacklist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()


async def is_blacklisted(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM blacklist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return await cursor.fetchone() is not None


async def get_blacklist(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM blacklist WHERE guild_id = ?", (guild_id,))
        return await cursor.fetchall()


async def add_whitelist(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO whitelist (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        await db.commit()


async def remove_whitelist(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()


async def is_whitelisted(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return await cursor.fetchone() is not None


async def get_whitelist(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM whitelist WHERE guild_id = ?", (guild_id,))
        return await cursor.fetchall()
