"""
utils/embeds.py — Sistema de Embeds para Choppa Security v6
Estilo: Negro + Silver Surfer + by choppa
"""
import discord
from datetime import datetime
from config import (
    COLOR_PRIMARY, COLOR_RED, COLOR_GREEN, COLOR_YELLOW,
    COLOR_BLUE, COLOR_ORANGE, BOT_IMAGE, BOT_NAME,
    BOT_VERSION, BOT_FOOTER
)


def create_embed(title, description, color=COLOR_PRIMARY, fields=None, image=None, thumbnail=None):
    """Crea un embed base con estilo Choppa Security"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_image(url=image or BOT_IMAGE)
    embed.set_footer(text=f"🛡️ {BOT_NAME} v{BOT_VERSION} • {BOT_FOOTER}")

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=str(value)[:1024], inline=inline)

    return embed


# ═══════════════════════════════════════════
#  EMBEDS DE SEGURIDAD
# ═══════════════════════════════════════════

def raid_detected(count, window):
    return create_embed(
        "🚨 RAID DETECTADO",
        f"**{count}** usuarios se unieron en **{window}** segundos",
        color=COLOR_RED,
        fields=[
            ("⚡ Acción", "Auto-ban de todos los involucrados", False),
            ("👥 Usuarios baneados", str(count), True),
            ("⏱️ Ventana", f"{window}s", True),
        ]
    )


def spam_detected(user, count):
    return create_embed(
        "🚫 SPAM DETECTADO",
        f"**{user.mention}** fue silenciado por spam",
        color=COLOR_RED,
        fields=[
            ("📝 Mensajes", str(count), True),
            ("🔇 Acción", "Mute automático", True),
        ]
    )


def link_blocked(user, link, warn_count):
    return create_embed(
        "🔗 LINK BLOQUEADO",
        f"**{user.mention}** — link eliminado",
        color=COLOR_RED,
        fields=[
            ("🔗 Link", f"||{link[:80]}||", False),
            ("⚠️ Warns", f"{warn_count}/5", True),
        ]
    )


def phishing_detected(user, link):
    return create_embed(
        "🎣 PHISHING DETECTADO",
        f"**{user.mention}** envió un link malicioso",
        color=COLOR_RED,
        fields=[
            ("🔗 Link malicioso", f"||{link[:80]}||", False),
            ("⚡ Acción", "Ban automático", True),
        ]
    )


def nsfw_detected(user):
    return create_embed(
        "🚫 CONTENIDO NSFW",
        f"**{user.mention}** fue baneado por contenido NSFW",
        color=COLOR_RED,
        fields=[
            ("⚡ Acción", "Ban automático", True),
            ("📋 Razón", "Contenido pornográfico/prohibido", False),
        ]
    )


def flood_detected(user, count, window):
    return create_embed(
        "⚡ FLOOD DETECTADO",
        f"**{user.mention}** — {count} mensajes en {window}s",
        color=COLOR_ORANGE,
        fields=[
            ("📝 Mensajes rápidos", str(count), True),
            ("⏱️ Ventana", f"{window}s", True),
            ("⚡ Acción", "Warn + Mute", True),
        ]
    )


def mention_spam(user, count):
    return create_embed(
        "📢 MENCIONES EXCESIVAS",
        f"**{user.mention}** mencionó a {count} personas",
        color=COLOR_RED,
        fields=[
            ("📢 Menciones", str(count), True),
            ("⚡ Acción", "Mensaje eliminado + Warn", True),
        ]
    )


def unauthorized_bot(user, inviter=None):
    desc = f"🤖 **{user}** fue baneado (bot no autorizado)"
    if inviter:
        desc += f"\n👤 **{inviter}** fue expulsado por invitarlo"
    return create_embed("🤖 BOT NO AUTORIZADO", desc, color=COLOR_RED)


# ═══════════════════════════════════════════
#  EMBEDS DE MODERACIÓN
# ═══════════════════════════════════════════

def user_banned(user, reason, moderator):
    return create_embed(
        "🔨 USUARIO BANEADO",
        f"**{user}** fue baneado del servidor",
        color=COLOR_RED,
        fields=[
            ("👤 Usuario", f"{user}\n`{user.id}`", True),
            ("📝 Razón", reason, True),
            ("👮 Moderador", moderator.mention, True),
        ]
    )


def user_kicked(user, reason, moderator):
    return create_embed(
        "👢 USUARIO EXPULSADO",
        f"**{user}** fue expulsado del servidor",
        color=COLOR_YELLOW,
        fields=[
            ("👤 Usuario", f"{user}\n`{user.id}`", True),
            ("📝 Razón", reason, True),
            ("👮 Moderador", moderator.mention, True),
        ]
    )


def user_muted(user, duration_min, reason):
    return create_embed(
        "🔇 USUARIO SILENCIADO",
        f"**{user.mention}** fue silenciado",
        color=COLOR_BLUE,
        fields=[
            ("⏱️ Duración", f"{duration_min} minutos", True),
            ("📝 Razón", reason, True),
        ]
    )


def user_warned(user, reason, warn_count, warn_limit):
    return create_embed(
        "⚠️ ADVERTENCIA",
        f"**{user.mention}** recibió una advertencia",
        color=COLOR_YELLOW,
        fields=[
            ("📝 Razón", reason, False),
            ("🔢 Warns", f"{warn_count}/{warn_limit}", True),
            ("⚠️ Siguiente", _next_action(warn_count, warn_limit), True),
        ]
    )


def _next_action(count, limit):
    if count >= 5:
        return "🔨 BAN automático"
    elif count >= 3:
        return "👢 KICK automático"
    elif count >= 2:
        return "🔇 MUTE automático"
    return "⚠️ Siguiente warn"


# ═══════════════════════════════════════════
#  EMBEDS DE INFO
# ═══════════════════════════════════════════

def security_status(guild, settings, total_warns=0):
    """Panel de estado de seguridad"""
    def on_off(val):
        return "✅" if val else "❌"

    return create_embed(
        "🛡️ ESTADO DE SEGURIDAD",
        f"Seguridad del servidor **{guild.name}**",
        color=COLOR_GREEN if settings else COLOR_RED,
        fields=[
            ("🚨 Anti-Raid", on_off(settings.get("anti_raid", True)), True),
            ("🚫 Anti-Spam", on_off(settings.get("anti_spam", True)), True),
            ("🔗 Anti-Links", "✅ Activo", True),
            ("🎣 Anti-Phishing", on_off(settings.get("anti_phishing", True)), True),
            ("📢 Auto-Mod", on_off(settings.get("auto_mod", True)), True),
            ("📝 Total Warns", str(total_warns), True),
            ("📊 Logs", on_off(settings.get("logs_enabled", True)), True),
        ]
    )


def owner_embed():
    """Embed del dueño del bot"""
    from config import OWNER_ID, OWNER_NAME, OWNER_DISCORD, OWNER_BIO
    return create_embed(
        f"👑 CREADOR DE {BOT_NAME.upper()}",
        f"Conoce al creador de **{BOT_NAME}**",
        color=COLOR_BLUE,
        fields=[
            ("👤 Nombre", OWNER_NAME, True),
            ("💬 Discord", f"`{OWNER_DISCORD}`", True),
            ("📋 ID", f"`{OWNER_ID}`", True),
            ("📝 Bio", OWNER_BIO, False),
            ("🤖 Sobre el Bot", f"**{BOT_NAME}** v{BOT_VERSION}\nBot de seguridad avanzado para Discord", False),
        ]
    )


def server_audit(guild, member_count, online_count, channel_count, role_count, emoji_count, boost_level):
    """Auditoría completa del servidor"""
    return create_embed(
        "📊 AUDITORÍA DEL SERVIDOR",
        f"Información completa de **{guild.name}**",
        color=COLOR_BLUE,
        fields=[
            ("👑 Dueño", f"<@{guild.owner_id}>\n`{guild.owner_id}`", True),
            ("📋 ID", f"`{guild.id}`", True),
            ("📅 Creado", f"<t:{int(guild.created_at.timestamp())}:R>", True),
            ("👥 Miembros", str(member_count), True),
            ("🟢 En línea", str(online_count), True),
            ("📁 Canales", str(channel_count), True),
            ("🎭 Roles", str(role_count), True),
            ("😀 Emojis", str(emoji_count), True),
            ("🚀 Nivel Boost", f"Nivel {boost_level}", True),
            ("🔒 Verificación", str(guild.verification_level).title(), True),
        ]
    )


def whois_embed(member, warn_count=0, is_blacklisted=False, is_whitelisted=False):
    """Info detallada de un usuario"""
    account_age = (datetime.utcnow() - member.created_at).days
    server_age = (datetime.utcnow() - member.joined_at).days if member.joined_at else 0
    roles = [r.mention for r in member.roles if r.name != "@everyone"]

    flags = [f for f in member.public_flags.all()]
    flag_str = ", ".join([str(f).split(".")[-1] for f in flags]) if flags else "Ninguna"

    return create_embed(
        f"🔍 INFORMACIÓN DE {member.name.upper()}",
        f"Análisis completo de **{member}**",
        color=COLOR_BLUE,
        fields=[
            ("👤 Usuario", f"{member}\n`{member.id}`", True),
            ("🤖 Bot", "Sí" if member.bot else "No", True),
            ("📅 Cuenta creada", f"<t:{int(member.created_at.timestamp())}:R>\n({account_age} días)", True),
            ("📥 Se unió", f"<t:{int(member.joined_at.timestamp())}:R>\n({server_age} días)" if member.joined_at else "N/A", True),
            ("🎭 Roles", " ".join(roles[:15]) if roles else "Ninguno", False),
            ("🔑 Permisos", flag_str, False),
            ("⚠️ Warns", str(warn_count), True),
            ("📋 Blacklist", "🔴 Sí" if is_blacklisted else "🟢 No", True),
            ("🛡️ Whitelist", "🟢 Sí" if is_whitelisted else "🔴 No", True),
        ]
    )


def owner_info():
    """Info completa del dueño"""
    from config import OWNER_ID, OWNER_NAME, OWNER_DISCORD, OWNER_BIO
    return create_embed(
        "👑 INFORMACIÓN DEL DUEÑO",
        f"Todo sobre el creador de **{BOT_NAME}**",
        color=COLOR_BLUE,
        fields=[
            ("👤 Nombre", OWNER_NAME, True),
            ("💬 Discord", OWNER_DISCORD, True),
            ("📋 ID", f"`{OWNER_ID}`", True),
            ("📝 Bio", OWNER_BIO, False),
            ("💎 Badges", "💎 Nitro • 🤖 Bot Developer • 🛡️ Security Expert", False),
            ("🤖 Bot", f"**{BOT_NAME}** v{BOT_VERSION}", True),
            ("🏆 Logros", "• Bot de seguridad más avanzado\n• 20+ protecciones activas\n• DMs automáticos en cada acción", False),
        ]
    )
