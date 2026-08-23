# ══════════════════════════════════════════════════════════════
#  config.py — Choppa Security v6.0
#  Configuración completa del bot de seguridad
# ══════════════════════════════════════════════════════════════

# ── Info del Bot ──────────────────────────────────
BOT_NAME = "Choppa Security"
BOT_VERSION = "6.0"
BOT_FOOTER = "by choppa"
BOT_IMAGE = "https://cdn.discordapp.com/attachments/1539487772946210890/1541176083078971392/ChatGPT_Image_23_ago_2026_04_02_14_p.m..png?ex=6a8ca393&is=6a8b5213&hm=95c24b195c1ad22da23f61a1225d03cbe7fbf2e027ba60fed3768bd35b4a768d"

# ── Colores ───────────────────────────────────────
COLOR_PRIMARY  = 0x000000   # Negro
COLOR_RED      = 0xFF0000   # Rojo
COLOR_GREEN    = 0x00FF00   # Verde
COLOR_YELLOW   = 0xFFFF00   # Amarillo
COLOR_BLUE     = 0x00BFFF   # Azul
COLOR_ORANGE   = 0xFF4500   # Naranja

# ── Owner ─────────────────────────────────────────
OWNER_ID = "1331303237315461163"
OWNER_NAME = "Choppa-?"
OWNER_DISCORD = "choppa"
OWNER_BIO = "Creador de Choppa Security — Bot de seguridad más avanzado de Discord"

# ── Seguridad ─────────────────────────────────────
SECURITY_ROLES = ["Admin", "Moderator", "Security", "Owner", "Administrador", "Moderador"]

# ── Anti-Raid ─────────────────────────────────────
RAID_JOIN_THRESHOLD = 5       # 5 joins en ventana → raid
RAID_TIME_WINDOW = 10         # 10 segundos

# ── Anti-Spam / Flood ─────────────────────────────
SPAM_THRESHOLD = 5            # 5 msgs en ventana → mute
SPAM_TIME_WINDOW = 5          # 5 segundos
FLOOD_THRESHOLD = 4           # 4 msgs en 3s → warn
FLOOD_TIME_WINDOW = 3
MUTE_DEFAULT_DURATION = 600   # 10 minutos

# ── Anti-Menciones ────────────────────────────────
MAX_MENTIONS = 4              # 4+ menciones → eliminar + DM

# ── Auto-Mod ──────────────────────────────────────
MAX_CAPS_PERCENT = 70
MIN_CAPS_LENGTH = 10
MAX_EMOJI_COUNT = 10
BLOCK_ALL_LINKS = True

# ── Warns ─────────────────────────────────────────
WARN_MUTE_THRESHOLD = 2
WARN_KICK_THRESHOLD = 3
WARN_BAN_THRESHOLD = 5

# ── NSFW ──────────────────────────────────────────
NSFW_KEYWORDS = [
    "nsfw", "porn", "xxx", "nude", "naked", "hentai",
    "onlyfans", "rule34", "ecchi", "lewd",
]

# ── Phishing Domains ──────────────────────────────
PHISHING_DOMAINS = [
    "discord.gift", "discοrd.gift", "discrl.com", "discorde.com",
    "steamcommunlty.com", "dlscord.gift", "discorcl.com",
    "gift-nitro.com", "free-nitro.com", "free-nitros.com",
]

# ── Palabras Prohibidas ──────────────────────────
BANNED_WORDS = [
    "nigger", "nigga", "faggot", "retard", "kike",
    "puto", "puta", "pendejo", "pendeja", "cabron",
    "hijo de puta", "hijodeputa", "estupido", "imbecil",
    "boludo", "boluda", "pelotudo", "forro",
    "cp", "nsfl", "gore",
]

# ── Nombres Sospechosos ──────────────────────────
SUSPICIOUS_NAMES = [
    "raid", "nuke", "destroy", "hack", "exploit",
    "spam", "bot", "test", "alt",
]

# ── Anti-Nuke ─────────────────────────────────────
NUKE_CHANNEL_DELETE = 3       # 3 canales eliminados en 10s
NUKE_CHANNEL_CREATE = 5       # 5 canales creados en 10s
NUKE_ROLE_DELETE = 3          # 3 roles eliminados en 10s
NUKE_TIME_WINDOW = 10

# ── Cuentas Nuevas ────────────────────────────────
ALT_ACCOUNT_DAYS = 7

# ── Logging ───────────────────────────────────────
LOG_CHANNEL_NAME = "security-logs"
