"""
database/db.py — Base de datos SQLite para el Bot de Seguridad
"""
import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "security.db")


async def init_db():
    """Inicializa la base de datos con todas las tablas necesarias"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Tabla de warns
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de logs de seguridad
        await db.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                moderator_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de configuración por servidor
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                anti_raid INTEGER DEFAULT 1,
                anti_spam INTEGER DEFAULT 1,
                anti_phishing INTEGER DEFAULT 1,
                auto_mod INTEGER DEFAULT 1,
                verification INTEGER DEFAULT 0,
                logs_enabled INTEGER DEFAULT 1,
                log_channel_id INTEGER,
                verification_channel_id INTEGER,
                verified_role_id INTEGER,
                welcome_channel_id INTEGER,
                raid_threshold INTEGER DEFAULT 5,
                raid_window INTEGER DEFAULT 10,
                spam_threshold INTEGER DEFAULT 5,
                spam_window INTEGER DEFAULT 5,
                mute_duration INTEGER DEFAULT 300,
                warn_kick_threshold INTEGER DEFAULT 3,
                warn_ban_threshold INTEGER DEFAULT 5
            )
        """)

        # Tabla de blacklist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de whitelist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de temp bans (para bans temporales)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS temp_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de verification captcha
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_verifications (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        await db.commit()


# ═══════════════════════════════════════════════
#  FUNCIONES DE WARNS
# ═══════════════════════════════════════════════

async def add_warn(guild_id, user_id, moderator_id, reason):
    """Agrega una advertencia a un usuario"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason)
        )
        await db.commit()
        return cursor.lastrowid


async def get_warns(guild_id, user_id):
    """Obtiene todas las advertencias de un usuario"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (guild_id, user_id)
        )
        return await cursor.fetchall()


async def get_warn_count(guild_id, user_id):
    """Obtiene el número total de advertencias"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM warns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def remove_warn(guild_id, warn_id):
    """Elimina una advertencia"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM warns WHERE guild_id = ? AND id = ?",
            (guild_id, warn_id)
        )
        await db.commit()


async def clear_warns(guild_id, user_id):
    """Limpia todas las advertencias de un usuario"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM warns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()


# ═══════════════════════════════════════════════
#  FUNCIONES DE LOGS
# ═══════════════════════════════════════════════

async def add_log(guild_id, event_type, user_id=None, moderator_id=None, details=None):
    """Agrega un log de seguridad"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO security_logs (guild_id, event_type, user_id, moderator_id, details) VALUES (?, ?, ?, ?, ?)",
            (guild_id, event_type, user_id, moderator_id, details)
        )
        await db.commit()


async def get_logs(guild_id, limit=50, event_type=None):
    """Obtiene logs de seguridad"""
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


# ═══════════════════════════════════════════════
#  FUNCIONES DE CONFIGURACIÓN
# ═══════════════════════════════════════════════

async def get_guild_settings(guild_id):
    """Obtiene la configuración de un servidor"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                'guild_id': row[0],
                'anti_raid': bool(row[1]),
                'anti_spam': bool(row[2]),
                'anti_phishing': bool(row[3]),
                'auto_mod': bool(row[4]),
                'verification': bool(row[5]),
                'logs_enabled': bool(row[6]),
                'log_channel_id': row[7],
                'verification_channel_id': row[8],
                'verified_role_id': row[9],
                'welcome_channel_id': row[10],
                'raid_threshold': row[11],
                'raid_window': row[12],
                'spam_threshold': row[13],
                'spam_window': row[14],
                'mute_duration': row[15],
                'warn_kick_threshold': row[16],
                'warn_ban_threshold': row[17],
            }
        return None


async def update_guild_settings(guild_id, **kwargs):
    """Actualiza la configuración de un servidor"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Verificar si existe
        cursor = await db.execute(
            "SELECT guild_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        exists = await cursor.fetchone()

        if not exists:
            await db.execute(
                "INSERT INTO guild_settings (guild_id) VALUES (?)",
                (guild_id,)
            )

        for key, value in kwargs.items():
            if value is not None:
                await db.execute(
                    f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?",
                    (value, guild_id)
                )

        await db.commit()


# ═══════════════════════════════════════════════
#  FUNCIONES DE BLACKLIST / WHITELIST
# ═══════════════════════════════════════════════

async def add_blacklist(guild_id, user_id, reason, added_by):
    """Agrega un usuario a la blacklist"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO blacklist (guild_id, user_id, reason, added_by) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, reason, added_by)
        )
        await db.commit()


async def remove_blacklist(guild_id, user_id):
    """Remueve un usuario de la blacklist"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM blacklist WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()


async def is_blacklisted(guild_id, user_id):
    """Verifica si un usuario está en la blacklist"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM blacklist WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return await cursor.fetchone() is not None


async def get_blacklist(guild_id):
    """Obtiene la blacklist completa"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM blacklist WHERE guild_id = ? ORDER BY created_at DESC",
            (guild_id,)
        )
        return await cursor.fetchall()


async def add_whitelist(guild_id, user_id, added_by):
    """Agrega un usuario a la whitelist"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO whitelist (guild_id, user_id, added_by) VALUES (?, ?, ?)",
            (guild_id, user_id, added_by)
        )
        await db.commit()


async def remove_whitelist(guild_id, user_id):
    """Remueve un usuario de la whitelist"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM whitelist WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()


async def is_whitelisted(guild_id, user_id):
    """Verifica si un usuario está en la whitelist"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM whitelist WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        return await cursor.fetchone() is not None


async def get_whitelist(guild_id):
    """Obtiene la whitelist completa"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM whitelist WHERE guild_id = ? ORDER BY created_at DESC",
            (guild_id,)
        )
        return await cursor.fetchall()


# ═══════════════════════════════════════════════
#  FUNCIONES DE TEMP BANS
# ═══════════════════════════════════════════════

async def add_temp_ban(guild_id, user_id, expires_at, reason):
    """Agrega un ban temporal"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO temp_bans (guild_id, user_id, expires_at, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, expires_at, reason)
        )
        await db.commit()


async def get_expired_bans():
    """Obtiene bans temporales expirados"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM temp_bans WHERE expires_at <= ?",
            (datetime.utcnow().isoformat(),)
        )
        return await cursor.fetchall()


async def remove_temp_ban(guild_id, user_id):
    """Remueve un ban temporal"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()
