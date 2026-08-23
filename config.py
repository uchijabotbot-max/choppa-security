# ─────────────────────────────────────────────
#  config.py — Configuración del Bot de Seguridad
# ─────────────────────────────────────────────

# ── Colores para Embeds ──────────────────────
COLOR_PRIMARY    = 0x000000   # Negro (principal)
COLOR_SECURITY   = 0xFF0000   # Rojo (seguridad)
COLOR_SUCCESS    = 0x00FF00   # Verde (éxito)
COLOR_WARNING    = 0xFFFF00   # Amarillo (advertencia)
COLOR_INFO       = 0x00BFFF   # Azul (información)
COLOR_DANGER     = 0xFF4500   # Rojo oscuro (peligro)

# ── Imagen del Bot ──────────────────────────
BOT_IMAGE = "https://media.discordapp.net/attachments/1477385853943812218/1479335985106915459/215_Silver_Surfer_4K_3840x2160p_OLED_Live_Wallpaper_2026_NEW__1_hour_-_YouTube_-_Google_Chrome_3_6_2026_12_31_19_AM.png?ex=6a8bc97f&is=6a8a77ff&hm=e8e51e82708c2fb47560d1eb2f14e59d846c038df421c8f3cd08d26d6c6a8423&=&format=webp&quality=lossless&width=1024&height=576"

# ── Info del Bot ──────────────────────────────
BOT_NAME = "Choppa Security"
BOT_VERSION = "5.0"
BOT_FOOTER = "by choppa"

# ── Info del Dueño / Creador ─────────────────
OWNER_NAME = "Choppa-?"
OWNER_ID = "1331303237315461163"
OWNER_STATUS = "https://Programer"
OWNER_BADGES = ["💎 Nitro", "🤖 Bot Developer", "🛡️ Security Expert"]
OWNER_DISCORD = "choppa"
OWNER_GITHUB = "https://github.com/uchijabotbot-max"
OWNER_BIO = "Creador de Choppa Security — Bot de seguridad más avanzado de Discord"
OWNER_AVATAR = "https://media.discordapp.net/attachments/1477385853943812218/1479335985106915459/215_Silver_Surfer_4K_3840x2160p_OLED_Live_Wallpaper_2026_NEW__1_hour_-_YouTube_-_Google_Chrome_3_6_2026_12_31_19_AM.png"

# ── Anti-Raid Config ──────────────────────────
RAID_JOIN_THRESHOLD = 5
RAID_TIME_WINDOW = 10

# ── Anti-Spam Config ──────────────────────────
SPAM_MESSAGE_THRESHOLD = 5
SPAM_TIME_WINDOW = 5
SPAM_MUTE_DURATION = 300

# ── Anti-Flood Config ─────────────────────────
# Si un usuario envía más de FLOOD_THRESHOLD mensajes en FLOOD_TIME_WINDOW segundos
FLOOD_THRESHOLD = 4          # 4 mensajes rápidos → advertencia
FLOOD_TIME_WINDOW = 3        # en 3 segundos
FLOOD_ACTION = "warn"        # warn, mute, kick, ban
FLOOD_MUTE_DURATION = 600    # 10 minutos de mute si es agresivo

# ── Anti-Mention Config ────────────────────────
# Si un usuario menciona más de MAX_MENTION_COUNT personas en un solo mensaje
MAX_MENTION_COUNT = 4        # 4+ menciones → eliminar + DM
MENTION_ACTION = "delete"    # delete, warn, mute, kick, ban

# ── Modo Agresivo ─────────────────────────────
# Activa todas las protecciones al máximo
AGGRESSIVE_MODE = True
AGGRESSIVE_BAN_ON_REPEAT = True   # Banear si repite infracción 3 veces
AGGRESSIVE_DM_ON_EVERY_ACTION = True  # Siempre enviar DM con info completa
AGGRESSIVE_LOG_EVERYTHING = True  # Loggear absolutamente todo
AGGRESSIVE_MAX_WARNINGS_BAN = 3   # 3 warnings → ban automático
AGGRESSIVE_AUTO_PURGE_LINKS = True  # Eliminar links sin avisar
AGGRESSIVE_ANTI_ALT_ACCOUNTS = True  # Detectar cuentas alternativas
ALT_ACCOUNT_DAYS = 7  # Cuentas con menos de 7 días son sospechosas

# ── Anti-Phishing / Anti-Links ────────────────
# Eliminar TODOS los links (no solo phishing)
BLOCK_ALL_LINKS = True

PHISHING_DOMAINS = [
    "discord.gift", "discοrd.gift", "discrl.com", "discorde.com",
    "steamcommunlty.com", "stearncommunnity.com", "dropx.me",
    "dlscord.gift", "discorcl.com", "discrcl.com",
    "gift-nitro.com", "free-nitro.com", "free-nitros.com",
    "steam-giveaway.com", "nitro-giveaway.com",
    "paypal-free.com", "crypto-gift.com",
]

# ── Auto-Mod Config ──────────────────────────
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
MIN_CAPS_LENGTH = 10
MAX_EMOJI_COUNT = 10

# Lista expandida de palabras prohibidas
BANNED_WORDS = [
    # Inglés
    "nigger", "nigga", "faggot", "retard", "kike", "spic", "chink",
    "cracker", "honky", "beaner", "wetback", "towelhead",
    # Español
    "puto", "puta", "mierda", "pendejo", "pendeja", "cabron", "cabrona",
    "estupido", "estupida", "imbecil", "idiota", "basura",
    "hijo de puta", "hijodeputa", "concha de tu madre",
    "la concha", "boludo", "boluda", "gil", "gila",
    "pelotudo", "pelotuda", "forro", "forra",
    "chorro", "chora", "gato", "gata",
    # Números ilegales / extremos
    "cp", "nsfl", "gore",
]

# ── Anti-NSFW / Imágenes ──────────────────────
NSFW_DETECTION_ENABLED = True
NSFW_KEYWORDS = [
    "nsfw", "porn", "xxx", "nude", "naked", "hentai",
    "onlyfans", "fap", "cum", "boobs", "ass",
    "penis", "vagina", "dick", "pussy",
    "sexcam", "camgirl", "camboy",
    "lewd", "ecchi", "rule34",
]

# ── Anti-Bots Maliciosos ──────────────────────
BAN_UNAUTHORIZED_BOTS = True

# ── Monitoreo de Administradores ──────────────
WATCH_ADMINS = True  # Monitorear acciones de admins

# ── Sistema de Warns ──────────────────────────
WARN_KICK_THRESHOLD = 3
WARN_BAN_THRESHOLD = 5
WARN_MUTE_THRESHOLD = 2

# ── Verification Config ───────────────────────
VERIFICATION_CHANNEL_NAME = "verificarse"
VERIFIED_ROLE_NAME = "Verificado"
VERIFICATION_TIMEOUT = 300

# ── Logging Config ────────────────────────────
LOG_CHANNEL_NAME = "security-logs"
AUDIT_LOG_ENABLED = True

# ── Canales de Seguridad ──────────────────────
SECURITY_ROLES = ["Admin", "Moderator", "Security", "Owner"]

# ══════════════════════════════════════════════════════════════
#  PROTECCIONES NUCLEARES (IMPARABLE)
# ══════════════════════════════════════════════════════════════

# ── Anti-Nuke Protection ──────────────────────
# Detecta y previene destrucción masiva del servidor
ANTI_NUKE_ENABLED = True
NUKE_CHANNEL_DELETE_THRESHOLD = 3   # 3 canales eliminados en 10s → nuke detectado
NUKE_CHANNEL_CREATE_THRESHOLD = 5   # 5 canales creados en 10s → nuke detectado
NUKE_BAN_THRESHOLD = 3              # 3 baneos en 10s → nuke detectado
NUKE_KICK_THRESHOLD = 5             # 5 kicks en 10s → nuke detectado
NUKE_ROLE_CREATE_THRESHOLD = 3      # 3 roles creados en 10s → nuke detectado
NUKE_TIME_WINDOW = 10               # Ventana de tiempo para detectar nuke
NUKE_ACTION = "ban"                  # Acción contra el nuker: ban, kick, all_permissions_removed

# ── Emergency Lockdown ────────────────────────
# Cierre de emergencia del servidor
LOCKDOWN_ENABLED = True
LOCKDOWN_COMMAND = "/lockdown"      # Comando para activar lockdown
LOCKDOWN_ROLES_AFFECTED = ["@everyone"]  # Roles afectados por lockdown
LOCKDOWN_CHANNEL_PERMISSIONS = {    # Permisos revocados durante lockdown
    "send_messages": False,
    "add_reactions": False,
    "create_public_threads": False,
    "create_private_threads": False,
}

# ── Auto-Lockdown During Raids ────────────────
# Cierre automático durante raids
AUTO_LOCKDOWN_ENABLED = True
AUTO_LOCKDOWN_THRESHOLD = 10        # 10 joins en 10s → lockdown automático
AUTO_LOCKDOWN_DURATION = 300         # 5 minutos de lockdown
AUTO_LOCKDOWN_CHANNELS = ["general", "chat", "texto"]  # Canales a bloquear

# ── Mass Action Detection ─────────────────────
# Detecta acciones masivas sospechosas
MASS_ACTION_DETECTION = True
MASS_BAN_THRESHOLD = 3              # 3 baneos en 10s
MASS_KICK_THRESHOLD = 5             # 5 kicks en 10s
MASS_CHANNEL_DELETE_THRESHOLD = 3   # 3 canales eliminados en 10s
MASS_CHANNEL_CREATE_THRESHOLD = 5   # 5 canales creados en 10s
MASS_ROLE_CREATE_THRESHOLD = 3      # 3 roles creados en 10s
MASS_ROLE_DELETE_THRESHOLD = 3      # 3 roles eliminados en 10s
MASS_ACTION_TIME_WINDOW = 10        # Ventana de tiempo

# ── Role Protection ───────────────────────────
# Protección contra creación/eliminación de roles maliciosos
ROLE_PROTECTION_ENABLED = True
ROLE_MAX_CREATE_PER_MINUTE = 3      # Máximo 3 roles creados por minuto
ROLE_PREVENT_HIGH_PERMISSION = True # Prevenir creación de roles con permisos altos
ROLE_BLOCKED_PERMISSIONS = [        # Permisos bloqueados en nuevos roles
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_channels",
    "manage_roles",
    "manage_webhooks",
    "manage_emojis",
]

# ── Webhook Protection ────────────────────────
# Protección contra webhooks maliciosos
WEBHOOK_PROTECTION_ENABLED = True
WEBHOOK_MAX_PER_CHANNEL = 5         # Máximo 5 webhooks por canal
WEBHOOK_DELETE_UNAUTHORIZED = True  # Eliminar webhooks no autorizados

# ── Suspicious Activity Detection ─────────────
# Detección de actividad sospechosa avanzada
SUSPICIOUS_ACTIVITY_DETECTION = True
SUSPICIOUS_JOIN_PATTERN = True      # Detectar patrones de join sospechosos
SUSPICIOUS_NAME_PATTERN = True      # Detectar nombres sospechosos
SUSPICIOUS_NAME_KEYWORDS = [        # Nombres sospechosos
    "raid", "nuke", "destroy", "hack", "exploit",
    "spam", "bot", "test", "alt", "dummy",
]

# ── Auto-Timeout New Members ──────────────────
# Timeout automático a nuevos miembros hasta que verifiquen
AUTO_TIMEOUT_NEW_MEMBERS = True
AUTO_TIMEOUT_DURATION = 600          # 10 minutos
AUTO_TIMEOUT_WHILE_UNVERIFIED = True

# ── Raid Alert Ping ───────────────────────────
# Ping a admins durante raids
RAID_ALERT_PING_ENABLED = True
RAID_ALERT_ROLE = "Admin"            # Rol a pingear durante raids
RAID_ALERT_MESSAGE = "🚨 RAID DETECTADO — ¡ACCIÓN INMEDIATA REQUERIDA!"

# ── Emergency Commands ────────────────────────
# Comandos de emergencia
EMERGENCY_LOCKDOWN_CMD = "/lockdown"    # Bloquear todos los canales
EMERGENCY_UNLOCK_CMD = "/unlockdown"    # Desbloquear todos los canales
EMERGENCY_NUKE_PREVENT_CMD = "/antinuke" # Prevenir nuke activo
EMERGENCY_MASS_BAN_CMD = "/massban"      # Banear múltiples usuarios
EMERGENCY_PURGE_CMD = "/purge"          # Limpiar mensajes
EMERGENCY_BACKUP_CMD = "/backup"        # Backup de configuración

# ── Backup System ─────────────────────────────
# Sistema de backup automático
BACKUP_ENABLED = True
BACKUP_INTERVAL = 3600                # Cada hora
BACKUP_CHANNEL = "bot-backups"         # Canal de backups
