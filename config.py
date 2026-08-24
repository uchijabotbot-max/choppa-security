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
RAID_JOIN_THRESHOLD = 3       # 3 joins en 5s → raid
RAID_TIME_WINDOW = 5          # 5 segundos

# ── Anti-Spam / Flood ─────────────────────────────
SPAM_THRESHOLD = 3            # 3 msgs en 5s → mute
SPAM_TIME_WINDOW = 5          # 5 segundos
FLOOD_THRESHOLD = 3           # 3 msgs en 2s → warn
FLOOD_TIME_WINDOW = 2
MUTE_DEFAULT_DURATION = 1800  # 30 minutos (antes 10)

# ── Anti-Menciones ────────────────────────────────
MAX_MENTIONS = 3              # 3+ menciones → eliminar + DM (antes 4)

# ── Auto-Mod ──────────────────────────────────────
MAX_CAPS_PERCENT = 50         # 50% mayusculas → delete (antes 70)
MIN_CAPS_LENGTH = 8           # Minimo 8 chars (antes 10)
MAX_EMOJI_COUNT = 7           # 7+ emojis → delete (antes 10)
BLOCK_ALL_LINKS = True

# ── Warns (mas agresivo) ─────────────────────────
WARN_MUTE_THRESHOLD = 1       # 1 warn → mute (antes 2)
WARN_KICK_THRESHOLD = 2       # 2 warns → kick (antes 3)
WARN_BAN_THRESHOLD = 3        # 3 warns → ban (antes 5)

# ── NSFW (lista expandida) ────────────────────────
NSFW_KEYWORDS = [
    "nsfw", "porn", "xxx", "nude", "naked", "hentai",
    "onlyfans", "rule34", "ecchi", "lewd",
    "fap", "cum", "boobs", "dick", "pussy",
    "sexcam", "camgirl", "camboy",
    "adult", "erotic", "fetish",
]

# ── Phishing Domains (lista expandida) ──────────────
PHISHING_DOMAINS = [
    "discord.gift", "disc0rd.gift", "discrl.com", "discorde.com",
    "steamcommunlty.com", "dlscord.gift", "discorcl.com",
    "gift-nitro.com", "free-nitro.com", "free-nitros.com",
    "discordgifts.com", "discocrd.com", "discorb.com",
    "steam-giveaway.com", "nitro-giveaway.com",
    "paypal-free.com", "crypto-gift.com",
    "roblox-free.com", "minecraft-free.com",
]

# ── Palabras Prohibidas ──────────────────────────
# Lista ULTRA de palabras prohibidas - banea automaticamente
BANNED_WORDS = [
    # Racismo / Odio
    "nigger", "nigga", "faggot", "retard", "kike",
    "spic", "chink", "cracker", "wetback", "beaner",
    "towelhead", "honky", "jap",
    # Sexismo
    "slut", "whore", "bitch", "hoe", "cunt",
    # Spanish
    "puto", "puta", "pendejo", "pendeja", "cabron", "cabrona",
    "hijo de puta", "hijodeputa", "concha de tu madre",
    "la concha", "estupido", "estupida", "imbecil", "idiota",
    "basura", "mierda", "mrd",
    "boludo", "boluda", "pelotudo", "pelotuda",
    "forro", "forra", "gil", "gila",
    "chorro", "chora", "gato", "gata",
    "zorra", "sapo", "rata",
    # Portugues
    "caralho", "porra", "foda", "desgraça", "arrombado",
    # Inglés vulgar
    "asshole", "dickhead", "dumbass", "motherfucker",
    "dick", "pussy", "penis", "vagina",
    "cum", "boobs", "tits", "ass",
    # Ilegales / Peligrosos
    "cp", "nsfl", "gore", "kill yourself", "kys",
    "suicide", "murder",
    # Slurs
    "tranny", "dyke", "fag", "fags",
]

# Palabras que causan BAN INMEDIATO (sin warnings)
BANNED_WORDS_BAN = [
    "kill yourself", "kys",
    "cp", "nsfl", "gore",
    "child porn",
]

# Numero de palabras prohibidas para ban automatico
BAD_WORD_BAN_THRESHOLD = 2   # 2 palabras malas = ban (antes 3)

# ── Nombres Sospechosos ──────────────────────────
SUSPICIOUS_NAMES = [
    "raid", "nuke", "destroy", "hack", "exploit",
    "spam", "bot", "test", "alt",
]

# ── Anti-Nuke ─────────────────────────────────────
NUKE_CHANNEL_DELETE = 2       # 2 canales eliminados en 5s
NUKE_CHANNEL_CREATE = 3       # 3 canales creados en 5s
NUKE_ROLE_DELETE = 2          # 2 roles eliminados en 5s
NUKE_TIME_WINDOW = 5

# ── Cuentas Nuevas ────────────────────────────────
ALT_ACCOUNT_DAYS = 14         # 14 dias (antes 7) - mas estricto

# ── Anti-Invite (bloquear links de invitacion) ──
ANTI_INVITE_ENABLED = True
INVITE_PATTERNS = [
    "discord.gg/", "discord.com/invite/",
    "dsc.gg/", "invite.gg/",
    "disboard.org/",
    "top.gg/",
    "discord.me/",
    "discordlist.gg/",
    "carbonitex.com/",
]

# ── Anti-Link Ultra Agresivo ─────────────────────
# Umbral para ban por links (1 link = warn, 2 = ban)
LINK_BAN_THRESHOLD = 2

# ── Anti-Mass Role Delete ──────────────────────
ANTI_ROLE_DELETE_ENABLED = True
ROLE_DELETE_THRESHOLD = 2     # 2 roles eliminados en 5s = nuke
ROLE_DELETE_TIME_WINDOW = 5

# ── Anti-Mass Kick ─────────────────────────────
ANTI_MASS_KICK_ENABLED = True
MASS_KICK_THRESHOLD = 2      # 2 kicks en 5s = ban
MASS_KICK_TIME_WINDOW = 5

# ── Anti-Mass Ban ──────────────────────────────
ANTI_MASS_BAN_ENABLED = True
MASS_BAN_THRESHOLD = 1       # 1 ban en 5s = sospechoso
MASS_BAN_TIME_WINDOW = 5

# ── Backup Automatico ──────────────────────────
BACKUP_ENABLED = True
BACKUP_INTERVAL_HOURS = 2    # Cada 2 horas (antes 6) - mas frecuente

# ── Deteccion de Acciones Anormales ──────────────
# Si alguien hace 5+ acciones destructivas en 5s = kick
ABNORMAL_ACTION_THRESHOLD = 5
ABNORMAL_ACTION_WINDOW = 5  # 5 segundos
# Acciones que cuentan: channel_delete, role_delete, channel_create,
# role_create, permission_update, ban, kick

# ── Anti-Aplicacion / Comandos ────────────────────
# Bloquear apps/integraciones no autorizadas
ANTI_APP_ENABLED = True
ALLOWED_APPS = []  # Apps permitidas (vacio = bloquear todas las nuevas)

# ── Logging ───────────────────────────────────────
LOG_CHANNEL_NAME = "security-logs"
