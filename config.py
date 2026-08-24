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

# ── Anti-Raid Ultra Agresivo ────────────────────
RAID_JOIN_THRESHOLD = 2       # 2 joins en 0.1s → raid
RAID_TIME_WINDOW = 0.1        # 0.1 segundos (ultra rapido)
# Auto-lockdown durante raid (bloquea todos los canales)
RAID_AUTO_LOCKDOWN = True
# Auto-ban todos los joins sospechosos durante raid
RAID_AUTO_BAN_ALL = True
# Ping a admins durante raid
RAID_PING_ADMINS = True
# Roles que pueden pingear durante raid
RAID_ALERT_ROLES = ["Admin", "Moderator", "Security", "Administrador", "Moderador"]
# Auto-lockdown durante raid (bloquea todos los canales)
RAID_AUTO_LOCKDOWN = True
# Auto-ban todos los joins sospechosos durante raid
RAID_AUTO_BAN_ALL = True
# Ping a admins durante raid
RAID_PING_ADMINS = True
# Roles que pueden pingear durante raid
RAID_ALERT_ROLES = ["Admin", "Moderator", "Security", "Administrador", "Moderador"]

# ── Anti-Spam / Flood ─────────────────────────────
SPAM_THRESHOLD = 2            # 2 msgs en 3s → mute
SPAM_TIME_WINDOW = 3          # 3 segundos
FLOOD_THRESHOLD = 2           # 2 msgs en 1s → warn
FLOOD_TIME_WINDOW = 1
MUTE_DEFAULT_DURATION = 3600  # 60 minutos

# ── Anti-Menciones ────────────────────────────────
MAX_MENTIONS = 2              # 2+ menciones → eliminar + DM

# ── Auto-Mod ──────────────────────────────────────
MAX_CAPS_PERCENT = 40         # 40% mayusculas → delete
MIN_CAPS_LENGTH = 5           # Minimo 5 chars
MAX_EMOJI_COUNT = 5           # 5+ emojis → delete
BLOCK_ALL_LINKS = True

# ── Warns (mas agresivo) ─────────────────────────
WARN_MUTE_THRESHOLD = 1       # 1 warn → mute
WARN_KICK_THRESHOLD = 2       # 2 warns → kick
WARN_BAN_THRESHOLD = 3        # 3 warns → ban

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
BAD_WORD_BAN_THRESHOLD = 1   # 1 palabra = ban inmediato

# ── Nombres Sospechosos ──────────────────────────
SUSPICIOUS_NAMES = [
    "raid", "nuke", "destroy", "hack", "exploit",
    "spam", "bot", "test", "alt",
]

# ── Anti-Nuke Ultra Agresivo ─────────────────────
NUKE_CHANNEL_DELETE = 1       # 1 canal eliminado en 3s → nuke
NUKE_CHANNEL_CREATE = 2       # 2 canales creados en 3s → nuke
NUKE_ROLE_DELETE = 1          # 1 rol eliminado en 3s → nuke
NUKE_ROLE_CREATE = 2          # 2 roles creados en 3s → nuke
NUKE_TIME_WINDOW = 3
# Auto-lockdown durante nuke
NUKE_AUTO_LOCKDOWN = True
# Auto-ban al responsable de nuke
NUKE_AUTO_BAN = True

# ── Cuentas Nuevas ────────────────────────────────
ALT_ACCOUNT_DAYS = 30         # 30 dias - ultra estricto

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
LINK_BAN_THRESHOLD = 1        # 1 link = ban inmediato

# ── Anti-Mass Role Delete ──────────────────────
ANTI_ROLE_DELETE_ENABLED = True
ROLE_DELETE_THRESHOLD = 1     # 1 rol eliminado en 3s = nuke
ROLE_DELETE_TIME_WINDOW = 3

# ── Anti-Mass Role Create ──────────────────────
ANTI_ROLE_CREATE_ENABLED = True
ROLE_CREATE_THRESHOLD = 2    # 2 roles creados en 3s = nuke
ROLE_CREATE_TIME_WINDOW = 3

# ── Anti-Mass Kick ─────────────────────────────
ANTI_MASS_KICK_ENABLED = True
MASS_KICK_THRESHOLD = 1      # 1 kick en 3s = ban
MASS_KICK_TIME_WINDOW = 3

# ── Anti-Mass Ban ──────────────────────────────
ANTI_MASS_BAN_ENABLED = True
MASS_BAN_THRESHOLD = 1       # 1 ban en 3s = alerta
MASS_BAN_TIME_WINDOW = 3

# ── Anti-Mass Channel Create ───────────────────
ANTI_MASS_CHANNEL_CREATE_ENABLED = True
MASS_CHANNEL_CREATE_THRESHOLD = 1  # 1 canal creado en 3s
MASS_CHANNEL_CREATE_TIME_WINDOW = 3

# ── Anti-Mass Channel Delete ───────────────────
ANTI_MASS_CHANNEL_DELETE_ENABLED = True
MASS_CHANNEL_DELETE_THRESHOLD = 1  # 1 canal eliminado en 3s
MASS_CHANNEL_DELETE_TIME_WINDOW = 3

# ── Anti-Mass Unban ────────────────────────────
ANTI_MASS_UNBAN_ENABLED = True
MASS_UNBAN_THRESHOLD = 2     # 2 unbans en 3s = sospechoso
MASS_UNBAN_TIME_WINDOW = 3

# ── Anti-Voice Raid ────────────────────────────
ANTI_VOICE_RAID_ENABLED = True
VOICE_RAID_THRESHOLD = 3     # 3 joins a voz en 3s
VOICE_RAID_TIME_WINDOW = 3

# ── Backup Automatico ──────────────────────────
BACKUP_ENABLED = True
BACKUP_INTERVAL_HOURS = 2    # Cada 2 horas (antes 6) - mas frecuente

# ── Deteccion de Acciones Anormales ──────────────
# Si alguien hace 3+ acciones destructivas en 3s = kick
ABNORMAL_ACTION_THRESHOLD = 3
ABNORMAL_ACTION_WINDOW = 3  # 3 segundos
# Acciones que cuentan: channel_delete, role_delete, channel_create,
# role_create, permission_update, ban, kick

# ── Anti-Aplicacion / Comandos ────────────────────
# Bloquear apps/integraciones no autorizadas
ANTI_APP_ENABLED = True
ALLOWED_APPS = []  # Apps permitidas (vacio = bloquear todas las nuevas)

# ── Logging ───────────────────────────────────────
LOG_CHANNEL_NAME = "security-logs"
