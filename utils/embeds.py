# ─────────────────────────────────────────────
#  embeds.py — Sistema de Embeds Avanzados
#  Tema: Negro + Silver Surfer + by choppa
# ─────────────────────────────────────────────
import discord
from datetime import datetime
from config import (
    COLOR_PRIMARY, COLOR_SECURITY, COLOR_SUCCESS,
    COLOR_WARNING, COLOR_INFO, COLOR_DANGER,
    BOT_IMAGE, BOT_NAME, BOT_VERSION, BOT_FOOTER
)


def create_embed(title, description, color=COLOR_PRIMARY, fields=None, image=None):
    """Crea un embed base con el estilo del bot"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    if image:
        embed.set_image(url=image)
    else:
        embed.set_image(url=BOT_IMAGE)
    
    embed.set_footer(
        text=f"🛡️ {BOT_NAME} v{BOT_VERSION} • {BOT_FOOTER}",
        icon_url="https://cdn.discordapp.com/attachments/1477385853943812218/1479335985106915459/215_Silver_Surfer_4K_3840x2160p_OLED_Live_Wallpaper_2026_NEW__1_hour_-_YouTube_-_Google_Chrome_3_6_2026_12_31_19_AM.png"
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    return embed


# ═══════════════════════════════════════════════
#  EMBEDS DE SEGURIDAD
# ═══════════════════════════════════════════════

def security_alert(title, description, severity="high"):
    """Embed de alerta de seguridad"""
    colors = {
        "critical": COLOR_DANGER,
        "high": COLOR_SECURITY,
        "medium": COLOR_WARNING,
        "low": COLOR_INFO
    }
    return create_embed(
        f"🚨 {title}",
        description,
        color=colors.get(severity, COLOR_SECURITY),
        fields=[
            ("⚠️ Severidad", severity.upper(), True),
            ("🕐 Hora", datetime.utcnow().strftime("%H:%M:%S UTC"), True),
        ]
    )


def raid_detected(count, time_window):
    """Embed de raid detectado"""
    return create_embed(
        "🚨 RAID DETECTADO",
        f"**{count}** miembros nuevos en **{time_window}** segundos",
        color=COLOR_DANGER,
        fields=[
            ("👥 Miembros detectados", str(count), True),
            ("⏱️ Ventana de tiempo", f"{time_window}s", True),
            ("🛡️ Acción tomada", "Banning automático", True),
        ]
    )


def spam_detected(user, message_count):
    """Embed de spam detectado"""
    return create_embed(
        "🚫 SPAM DETECTADO",
        f"**{user.mention}** está enviando mensajes demasiado rápido",
        color=COLOR_WARNING,
        fields=[
            ("👤 Usuario", user.mention, True),
            ("💬 Mensajes", str(message_count), True),
            ("🔇 Acción", "Mute temporal", True),
        ]
    )


def phishing_detected(user, url):
    """Embed de phishing detectado"""
    return create_embed(
        "钓鱼 PHISHING DETECTADO",
        f"**{user.mention}** envió un link sospechoso",
        color=COLOR_DANGER,
        fields=[
            ("👤 Usuario", user.mention, True),
            ("🔗 Link", f"||{url}||", False),
            ("⚠️ Acción", "Mensaje eliminado + Warn", True),
        ]
    )


def user_warned(user, reason, warn_count):
    """Embed de advertencia"""
    return create_embed(
        "⚠️ ADVERTENCIA",
        f"**{user.mention}** ha recibido una advertencia",
        color=COLOR_WARNING,
        fields=[
            ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
            ("📝 Razón", reason, True),
            ("🔢 Total warns", f"{warn_count}/5", True),
        ]
    )


def user_kicked(user, reason, moderator):
    """Embed de expulsión"""
    return create_embed(
        "👢 USUARIO EXPULSADO",
        f"**{user.mention}** ha sido expulsado del servidor",
        color=COLOR_SECURITY,
        fields=[
            ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
            ("📝 Razón", reason, True),
            ("👮 Moderador", moderator.mention, True),
        ]
    )


def user_banned(user, reason, moderator):
    """Embed de baneo"""
    return create_embed(
        "🔨 USUARIO BANEADO",
        f"**{user.mention}** ha sido baneado permanentemente",
        color=COLOR_DANGER,
        fields=[
            ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
            ("📝 Razón", reason, True),
            ("👮 Moderador", moderator.mention, True),
        ]
    )


def user_muted(user, duration, reason):
    """Embed de mute"""
    return create_embed(
        "🔇 USUARIO SILENCIADO",
        f"**{user.mention}** ha sido silenciado",
        color=COLOR_SECURITY,
        fields=[
            ("👤 Usuario", user.mention, True),
            ("⏱️ Duración", f"{duration} segundos", True),
            ("📝 Razón", reason, True),
        ]
    )


def member_joined(member):
    """Embed de miembro que entra"""
    account_age = (datetime.utcnow() - member.created_at).days
    is_suspicious = account_age < 7
    
    return create_embed(
        "📥 MIEMBRO NUEVO",
        f"**{member.mention}** se unió al servidor",
        color=COLOR_WARNING if is_suspicious else COLOR_SUCCESS,
        fields=[
            ("👤 Usuario", f"{member}\n`{member.id}`", True),
            ("📅 Cuenta creada", f"Hace {account_age} días", True),
            ("⚠️ Sospechoso", "SÍ" if is_suspicious else "NO", True),
            ("👥 Total miembros", str(member.guild.member_count), True),
        ]
    )


def member_left(member):
    """Embed de miembro que sale"""
    return create_embed(
        "📤 MIEMBRO SALIÓ",
        f"**{member}** salió del servidor",
        color=COLOR_INFO,
        fields=[
            ("👤 Usuario", f"`{member}`\n`{member.id}`", True),
            ("👥 Total miembros", str(member.guild.member_count), True),
        ]
    )


def message_deleted(message, moderator=None):
    """Embed de mensaje eliminado"""
    return create_embed(
        "🗑️ MENSAJE ELIMINADO",
        f"Mensaje de **{message.author.mention}** eliminado en {message.channel.mention}",
        color=COLOR_SECURITY,
        fields=[
            ("👤 Autor", message.author.mention, True),
            ("📍 Canal", message.channel.mention, True),
            ("📝 Contenido", message.content[:1024] if message.content else "*Sin contenido*", False),
            ("👮 Eliminado por", moderator.mention if moderator else "AutoMod", True),
        ]
    )


def message_edited(before, after):
    """Embed de mensaje editado"""
    return create_embed(
        "✏️ MENSAJE EDITADO",
        f"**{before.author.mention}** editó un mensaje en {before.channel.mention}",
        color=COLOR_INFO,
        fields=[
            ("👤 Autor", before.author.mention, True),
            ("📍 Canal", before.channel.mention, True),
            ("📝 Antes", before.content[:1024] if before.content else "*Sin contenido*", False),
            ("📝 Después", after.content[:1024] if after.content else "*Sin contenido*", False),
        ]
    )


def voice_state_update(member, before, after):
    """Embed de cambio de estado de voz"""
    action = ""
    if before.channel is None and after.channel is not None:
        action = f"🔊 **{member.mention}** se conectó a **{after.channel.name}**"
    elif before.channel is not None and after.channel is None:
        action = f"🔇 **{member.mention}** se desconectó de **{before.channel.name}**"
    elif before.channel != after.channel:
        action = f"🔀 **{member.mention}** se movió de **{before.channel.name}** a **{after.channel.name}**"
    
    if action:
        return create_embed(
            "🔊 CAMBIO DE VOZ",
            action,
            color=COLOR_INFO,
            fields=[
                ("👤 Usuario", member.mention, True),
                ("📍 Canal", after.channel.name if after.channel else "Desconectado", True),
            ]
        )
    return None


# ═══════════════════════════════════════════════
#  EMBEDS DE COMANDOS
# ═══════════════════════════════════════════════

def welcome_embed(member):
    """Embed de bienvenida"""
    return create_embed(
        f"🎉 ¡Bienvenido, {member.name}!",
        f"Has sido verificado correctamente.\n¡Disfruta tu estancia en **{member.guild.name}**!",
        color=COLOR_SUCCESS,
        fields=[
            ("📋 Reglas", "Lee las reglas en #reglas", True),
            ("💬 Chat", "¡Diviértete en los canales!", True),
        ]
    )


def security_panel():
    """Panel de comandos de seguridad"""
    return create_embed(
        "🛡️ PANEL DE SEGURIDAD COMPLETO",
        "Todos los comandos disponibles para la moderación y seguridad del servidor",
        color=COLOR_PRIMARY,
        fields=[
            ("🔨 Moderación", 
             "`/ban` - Banear usuario\n"
             "`/kick` - Expulsar usuario\n"
             "`/mute` - Silenciar usuario\n"
             "`/warn` - Advertir usuario\n"
             "`/unban` - Desbanear usuario\n"
             "`/unmute` - Quitar silencio\n"
             "`/clearwarns` - Limpiar warns\n"
             "`/warns` - Ver warns de un usuario", False),
            ("🛡️ Seguridad",
             "`/raid` - Configurar anti-raid\n"
             "`/antispam` - Configurar anti-spam\n"
             "`/whitelist` - Whitelist (inmune a todo)\n"
             "`/unwhitelist` - Remover de whitelist\n"
             "`/wl` - Ver whitelist\n"
             "`/blacklist` - Blacklist (auto-ban)\n"
             "`/unblacklist` - Remover de blacklist", False),
            ("🚨 Nuclear",
             "`/lockdown` - Bloquear todos los canales\n"
             "`/unlockdown` - Desbloquear canales\n"
             "`/antinuke` - Activar Anti-Nuke\n"
             "`/emergency` - Comandos de emergencia", False),
            ("📊 Auditoría",
             "`/serveraudit` - Auditoría COMPLETA del servidor\n"
             "`/whois` - Investigación ultra-detallada\n"
             "`/massaudit` - Auditar múltiples usuarios\n"
             "`/invites` - Ver todas las invitaciones\n"
             "`/securityscore` - Calificación de seguridad\n"
             "`/pingall` - Ping a todos los admins", False),
            ("📊 Info",
             "`/userinfo` - Info de un usuario\n"
             "`/serverinfo` - Info del servidor\n"
             "`/security` - Estado de seguridad\n"
             "`/securityinfo` - Reporte completo\n"
             "`/usersecurity` - Seguridad de un usuario\n"
             "`/logs` - Ver logs recientes\n"
             "`/members` - Estadísticas\n"
             "`/config` - Ver configuración\n"
             "`/toggle` - Activar/desactivar sistemas\n"
             "`/botinfo` - Info del bot\n"
             "`/ping` - Latencia del bot", False),
            ("👑 Creador",
             "`/owner` - Info del creador del bot\n"
             "`/creator` - Alternativa: Info del creador\n"
             "`/creditos` - Créditos del bot", False),
            ("⚡ Protecciones Activas",
             "✅ Anti-Flood (4 msgs rápidos)\n"
             "✅ Anti-Menciones (4+ menciones)\n"
             "✅ Anti-Links (todos los links)\n"
             "✅ Anti-Phishing\n"
             "✅ Anti-NSFW (auto-ban)\n"
             "✅ Anti-Bots no autorizados\n"
             "✅ Anti-Nuke (destrucción masiva)\n"
             "✅ Role Protection\n"
             "✅ Webhook Protection\n"
             "✅ Auto-Lockdown durante raids\n"
             "✅ Palabras prohibidas\n"
             "✅ Detección de cuentas alt\n"
             "✅ Monitoreo de admins", False),
        ]
    )


def userinfo_embed(member):
    """Embed de información de usuario"""
    roles = [role.mention for role in member.roles[1:]]
    roles_text = ", ".join(roles[:10]) if roles else "Sin roles"
    
    account_age = (datetime.utcnow() - member.created_at).days
    join_age = (datetime.utcnow() - member.joined_at).days if member.joined_at else "Desconocido"
    
    is_suspicious = account_age < 7
    
    return create_embed(
        f"👤 Información de {member.name}",
        f"**{member.mention}**",
        color=COLOR_SECURITY if is_suspicious else COLOR_PRIMARY,
        fields=[
            ("📋 ID", f"`{member.id}`", True),
            ("📅 Cuenta creada", f"<t:{int(member.created_at.timestamp())}:R>", True),
            ("📥 Se unió", f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Desconocido", True),
            ("🔢 Edad de cuenta", f"{account_age} días", True),
            ("⚠️ Sospechoso", "SÍ ⚠️" if is_suspicious else "NO ✅", True),
            ("🎭 Roles", roles_text[:1024], False),
        ]
    )


def serverinfo_embed(guild):
    """Embed de información del servidor"""
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    total_members = guild.member_count
    online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
    bots = sum(1 for m in guild.members if m.bot)
    
    return create_embed(
        f"🏠 Información de {guild.name}",
        f"**{guild.description}**" if guild.description else "Servidor de Discord",
        color=COLOR_PRIMARY,
        fields=[
            ("👑 Dueño", guild.owner.mention if guild.owner else "Desconocido", True),
            ("📅 Creado", f"<t:{int(guild.created_at.timestamp())}:R>", True),
            ("👥 Miembros", f"{total_members} total\n{online_members} en línea\n{bots} bots", True),
            ("💬 Canales", f"{text_channels} texto\n{voice_channels} voz", True),
            ("🛡️ Roles", str(len(guild.roles)), True),
            ("📊 Boosts", f"Nivel {guild.premium_tier}\n{guild.premium_subscription_count} boosts", True),
        ]
    )


def security_status_embed(guild, settings):
    """Embed de estado de seguridad"""
    return create_embed(
        "🛡️ ESTADO DE SEGURIDAD",
        f"Configuración actual de **{guild.name}**",
        color=COLOR_PRIMARY,
        fields=[
            ("🚨 Anti-Raid", "✅ Activo" if settings.get('anti_raid') else "❌ Inactivo", True),
            ("🚫 Anti-Spam", "✅ Activo" if settings.get('anti_spam') else "❌ Inactivo", True),
            ("🎣 Anti-Phishing", "✅ Activo" if settings.get('anti_phishing') else "❌ Inactivo", True),
            ("✅ Verificación", "✅ Activo" if settings.get('verification') else "❌ Inactivo", True),
            ("📝 Auto-Mod", "✅ Activo" if settings.get('auto_mod') else "❌ Inactivo", True),
            ("📊 Logs", "✅ Activo" if settings.get('logs') else "❌ Inactivo", True),
        ]
    )
