# ─────────────────────────────────────────────
#  cogs/security.py — Motor de Seguridad v3
#  Anti-Raid, Anti-Spam, Anti-Phishing, Anti-Links
#  Anti-NSFW, Anti-Bots, Monitoreo de Admins
# ─────────────────────────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict
import time
import re
import asyncio
import aiohttp
from datetime import datetime, timedelta

from config import (
    RAID_JOIN_THRESHOLD, RAID_TIME_WINDOW, SPAM_MESSAGE_THRESHOLD,
    SPAM_TIME_WINDOW, SPAM_MUTE_DURATION, MAX_MENTIONS,
    MAX_CAPS_PERCENT, MIN_CAPS_LENGTH, MAX_EMOJI_COUNT,
    BANNED_WORDS, PHISHING_DOMAINS, SECURITY_ROLES,
    BLOCK_ALL_LINKS, NSFW_DETECTION_ENABLED, NSFW_KEYWORDS,
    BAN_UNAUTHORIZED_BOTS, WATCH_ADMINS,
    FLOOD_THRESHOLD, FLOOD_TIME_WINDOW, FLOOD_ACTION, FLOOD_MUTE_DURATION,
    MAX_MENTION_COUNT, MENTION_ACTION,
    AGGRESSIVE_MODE, AGGRESSIVE_BAN_ON_REPEAT, AGGRESSIVE_DM_ON_EVERY_ACTION,
    AGGRESSIVE_LOG_EVERYTHING, AGGRESSIVE_MAX_WARNINGS_BAN,
    AGGRESSIVE_AUTO_PURGE_LINKS, AGGRESSIVE_ANTI_ALT_ACCOUNTS, ALT_ACCOUNT_DAYS,
    BOT_NAME
)
from utils.embeds import (
    raid_detected, spam_detected, phishing_detected,
    security_alert, message_deleted, create_embed
)
from database import db


class SecurityCog(commands.Cog):
    """Motor de seguridad principal del bot — Versión Ultra"""

    def __init__(self, bot):
        self.bot = bot
        self.join_times = defaultdict(list)
        self.message_times = defaultdict(list)
        self.raid_alerts = {}
        self.flood_tracker = defaultdict(list)  # user_id -> [timestamps]
        self.infraction_count = defaultdict(int)  # user_id -> count
        self.link_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*|'
            r'www\.(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*|'
            r'discord\.gg/[a-zA-Z0-9]+|'
            r'discord\.com/invite/[a-zA-Z0-9]+',
            re.IGNORECASE
        )

    # ═══════════════════════════════════════════
    #  EVENTOS DE SEGURIDAD
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Detecta raids, bots maliciosos y miembros nuevos"""
        if member.bot:
            # Auto-ban de bots no autorizados
            if BAN_UNAUTHORIZED_BOTS:
                await self._handle_unauthorized_bot(member)
            return

        settings = await db.get_guild_settings(member.guild.id)
        if not settings:
            await db.update_guild_settings(member.guild.id)

        # Anti-Raid
        if settings and settings.get('anti_raid', True):
            await self._check_raid(member)

        # Anti-Alt Account Detection
        await self._check_alt_account(member)

        # Auto-blacklist check
        if await db.is_blacklisted(member.guild.id, member.id):
            try:
                await member.ban(reason="Auto-ban: usuario en blacklist")
                await self._log_and_dm(
                    member.guild, "blacklist_ban", member,
                    "Auto-ban por estar en la blacklist"
                )
            except discord.Forbidden:
                pass

        # Log de nuevo miembro
        await self._log_security(member.guild, "member_join", member.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log de miembro que sale"""
        await self._log_security(member.guild, "member_leave", member.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Motor de seguridad para mensajes — ULTRA"""
        if message.author.bot or not message.guild:
            return

        settings = await db.get_guild_settings(message.guild.id)
        if not settings:
            return

        # Verificar whitelist (inmune a todo)
        if await db.is_whitelisted(message.guild.id, message.author.id):
            return

        # Anti-Flood (mensajes rápidos)
        if settings.get('anti_spam', True):
            if await self._check_flood(message):
                return

        # Anti-Spam
        if settings.get('anti_spam', True):
            if await self._check_spam(message):
                return

        # Anti-Mención (4+ menciones)
        if settings.get('auto_mod', True):
            if await self._check_mentions(message):
                return

        # Anti-Links (ELIMINAR TODOS los links)
        if BLOCK_ALL_LINKS:
            if await self._check_links(message):
                return

        # Anti-Phishing
        if settings.get('anti_phishing', True):
            if await self._check_phishing(message):
                return

        # Anti-NSFW (detectar imágenes/links NSFW)
        if NSFW_DETECTION_ENABLED:
            if await self._check_nsfw(message):
                return

        # Auto-Mod
        if settings.get('auto_mod', True):
            await self._check_auto_mod(message, settings)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log de mensajes eliminados"""
        if message.author.bot or not message.guild:
            return
        await self._log_security(
            message.guild, "message_delete", message.author.id,
            details=f"Canal: {message.channel.mention} | Contenido: {message.content[:200]}"
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log de mensajes editados"""
        if before.author.bot or not before.guild:
            return
        if before.content != after.content:
            await self._log_security(
                before.guild, "message_edit", before.author.id,
                details=f"Canal: {before.channel.mention}"
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Log de cambios de voz"""
        if member.bot:
            return
        action = ""
        if before.channel is None and after.channel:
            action = f"Conectado a {after.channel.name}"
        elif before.channel and after.channel is None:
            action = f"Desconectado de {before.channel.name}"
        elif before.channel != after.channel:
            action = f"Movido a {after.channel.name if after.channel else 'Ninguno'}"

        if action:
            await self._log_security(member.guild, "voice_state", member.id, details=action)

    # ═══════════════════════════════════════════
    #  MONITOREO DE ADMINISTRADORES
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Detecta cuando un admin elimina un canal"""
        if not WATCH_ADMINS:
            return

        guild = channel.guild
        # Buscar en el audit log quién lo hizo
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    moderator = entry.user

                    # No castigar a otros admins del bot
                    if moderator.bot:
                        return

                    # Verificar si es admin/mod
                    is_admin = any(role.name in ["Admin", "Owner", "Administrator"] for role in moderator.roles)

                    if is_admin:
                        # DM al admin con info completa
                        try:
                            dm_embed = create_embed(
                                "🚨 ACCIÓN DE SEGURIDAD DETECTADA",
                                f"Eliminaste el canal **#{channel.name}** en **{guild.name}**",
                                color=0xFF0000,
                                fields=[
                                    ("📍 Canal eliminado", f"#{channel.name}\n`ID: {channel.id}`", True),
                                    ("📝 Tipo", str(channel.type), True),
                                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                    ("⚠️ Razón", "Las acciones de eliminación de canales son monitoreadas por seguridad.", False),
                                    ("🛡️ Bot", f"**{BOT_NAME}** está vigilando", False),
                                ]
                            )
                            await moderator.send(embed=dm_embed)
                        except discord.Forbidden:
                            pass

                        # Log de seguridad
                        await self._log_security(
                            guild, "admin_channel_delete", moderator.id,
                            details=f"Canal eliminado: #{channel.name} (ID: {channel.id})"
                        )
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Detecta cuando un admin edita un canal"""
        if not WATCH_ADMINS:
            return

        guild = before.guild

        # Solo detectar cambios significativos
        changes = []
        if before.name != after.name:
            changes.append(f"Nombre: #{before.name} → #{after.name}")
        if before.topic != after.topic:
            changes.append("Tema modificado")
        if before.overwrites != after.overwrites:
            changes.append("Permisos modificados")

        if not changes:
            return

        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id:
                    moderator = entry.user

                    if moderator.bot:
                        return

                    is_admin = any(role.name in ["Admin", "Owner", "Administrator"] for role in moderator.roles)

                    if is_admin:
                        # DM al admin
                        try:
                            dm_embed = create_embed(
                                "✏️ CANAL EDITADO",
                                f"Editaste el canal **#{after.name}** en **{guild.name}**",
                                color=0xFFFF00,
                                fields=[
                                    ("📍 Canal", f"#{after.name}\n`ID: {after.id}`", True),
                                    ("📝 Cambios", "\n".join(changes), False),
                                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                    ("⚠️ Nota", "Las ediciones de canales son monitoreadas.", False),
                                ]
                            )
                            await moderator.send(embed=dm_embed)
                        except discord.Forbidden:
                            pass

                        await self._log_security(
                            guild, "admin_channel_update", moderator.id,
                            details=f"Canal editado: #{after.name} | Cambios: {', '.join(changes)}"
                        )
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Detecta cuando alguien banea a un usuario"""
        if not WATCH_ADMINS:
            return

        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator = entry.user

                    if moderator.bot:
                        return

                    is_admin = any(role.name in ["Admin", "Owner", "Administrator"] for role in moderator.roles)

                    if is_admin:
                        # DM al admin
                        try:
                            dm_embed = create_embed(
                                "🔨 BAN REALIZADO",
                                f"Baneaste a **{user}** en **{guild.name}**",
                                color=0xFF0000,
                                fields=[
                                    ("👤 Usuario baneado", f"{user}\n`ID: {user.id}`", True),
                                    ("📝 Razón", entry.reason or "Sin razón", True),
                                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                    ("⚠️ Nota", "Las acciones de baneo son monitoreadas.", False),
                                ]
                            )
                            await moderator.send(embed=dm_embed)
                        except discord.Forbidden:
                            pass

                        # DM al baneado
                        try:
                            ban_embed = create_embed(
                                "🔨 HAS SIDO BANEADO",
                                f"Fuiste baneado de **{guild.name}**",
                                color=0xFF0000,
                                fields=[
                                    ("👮 Moderador", str(moderator), True),
                                    ("📝 Razón", entry.reason or "Sin razón", True),
                                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                    ("📋 ID de usuario", f"`{user.id}`", True),
                                ]
                            )
                            await user.send(embed=ban_embed)
                        except discord.Forbidden:
                            pass

                        await self._log_security(
                            guild, "admin_ban", moderator.id, user.id,
                            details=f"Ban a {user} | Razón: {entry.reason}"
                        )
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Log de unbans"""
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    moderator = entry.user
                    await self._log_security(
                        guild, "admin_unban", moderator.id, user.id,
                        details=f"Unban de {user}"
                    )

                    # DM al usuario desbaneado
                    try:
                        dm_embed = create_embed(
                            "✅ HAS SIDO DESBANEADO",
                            f"Fuiste desbaneado de **{guild.name}**",
                            color=0x00FF00,
                            fields=[
                                ("👮 Moderador", str(moderator), True),
                                ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                ("🎉 Ahora puedes volver", "Únete de nuevo al servidor", True),
                            ]
                        )
                        await user.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    # ═══════════════════════════════════════════
    #  SISTEMAS DE SEGURIDAD
    # ═══════════════════════════════════════════

    async def _check_raid(self, member):
        """Sistema anti-raid avanzado"""
        guild_id = member.guild.id
        now = time.time()

        self.join_times[guild_id].append(now)
        self.join_times[guild_id] = [
            t for t in self.join_times[guild_id] if now - t < RAID_TIME_WINDOW
        ]

        join_count = len(self.join_times[guild_id])
        settings = await db.get_guild_settings(guild_id)
        threshold = settings.get('raid_threshold', RAID_JOIN_THRESHOLD) if settings else RAID_JOIN_THRESHOLD

        if join_count >= threshold:
            if guild_id in self.raid_alerts and now - self.raid_alerts[guild_id] < 60:
                return

            self.raid_alerts[guild_id] = now

            # Enviar alerta
            log_channel_id = settings.get('log_channel_id') if settings else None
            if log_channel_id:
                channel = member.guild.get_channel(log_channel_id)
                if channel:
                    embed = raid_detected(join_count, RAID_TIME_WINDOW)
                    await channel.send(embed=embed)

            # Banear miembros sospechosos
            recent_joins = [
                m for m in member.guild.members
                if (datetime.utcnow() - m.joined_at).total_seconds() < RAID_TIME_WINDOW
                and not m.bot
            ]

            for m in recent_joins:
                try:
                    await m.ban(reason=f"Anti-Raid: parte de un raid ({join_count} joins en {RAID_TIME_WINDOW}s)")

                    # DM al baneado
                    try:
                        dm = create_embed(
                            "🚨 BAN POR RAID",
                            f"Fuiste baneado de **{member.guild.name}** por ser parte de un raid.",
                            color=0xFF0000,
                            fields=[
                                ("📝 Razón", f"Parte de un raid ({join_count} joins en {RAID_TIME_WINDOW}s)", False),
                                ("📋 ID", f"`{m.id}`", True),
                            ]
                        )
                        await m.send(embed=dm)
                    except discord.Forbidden:
                        pass

                    await self._log_security(member.guild, "raid_ban", m.id,
                                             details=f"Auto-ban por raid ({join_count} joins)")
                    await asyncio.sleep(0.5)
                except discord.Forbidden:
                    pass

    async def _check_spam(self, message):
        """Sistema anti-spam avanzado"""
        user_id = message.author.id
        now = time.time()

        self.message_times[user_id].append(now)
        self.message_times[user_id] = [
            t for t in self.message_times[user_id] if now - t < SPAM_TIME_WINDOW
        ]

        msg_count = len(self.message_times[user_id])
        settings = await db.get_guild_settings(message.guild.id)
        threshold = settings.get('spam_threshold', SPAM_MESSAGE_THRESHOLD) if settings else SPAM_MESSAGE_THRESHOLD

        if msg_count >= threshold:
            mute_duration = settings.get('mute_duration', SPAM_MUTE_DURATION) if settings else SPAM_MUTE_DURATION
            timeout_until = discord.utils.utcnow() + timedelta(seconds=mute_duration)

            try:
                await message.author.timeout(timeout_until, reason=f"Anti-Spam: {msg_count} mensajes en {SPAM_TIME_WINDOW}s")

                embed = spam_detected(message.author, msg_count)
                await message.channel.send(embed=embed, delete_after=10)

                # DM al usuario
                try:
                    from utils.embeds import user_muted
                    dm_embed = user_muted(message.author, mute_duration,
                                          f"Anti-Spam: {msg_count} mensajes en {SPAM_TIME_WINDOW}s")
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                await self._log_security(message.guild, "spam_mute", message.author.id,
                                         moderator_id=self.bot.user.id,
                                         details=f"Mute por spam: {msg_count} msgs en {SPAM_TIME_WINDOW}s")

                self.message_times[user_id] = []
                return True
            except discord.Forbidden:
                pass
        return False

    async def _check_links(self, message):
        """ELIMINA TODOS los links y notifica al usuario"""
        content = message.content
        urls = self.link_pattern.findall(content)

        if not urls:
            return False

        # Verificar si es canal permitido (reglas, links, etc.)
        allowed_channels = ["reglas", "rules", "links", "recursos", "resources"]
        if any(ch in message.channel.name.lower() for ch in allowed_channels):
            return False

        # Eliminar el mensaje
        try:
            await message.delete()
        except discord.Forbidden:
            return False

        # Warn al usuario
        from database.db import add_warn, get_warn_count
        await add_warn(message.guild.id, message.author.id, self.bot.user.id,
                       f"Link enviado: {urls[0][:100]}")
        warn_count = await get_warn_count(message.guild.id, message.author.id)

        # Embed de alerta en el canal
        alert_embed = create_embed(
            "🔗 LINK BLOQUEADO",
            f"**{message.author.mention}**, los links no están permitidos en este canal.",
            color=0xFF0000,
            fields=[
                ("📍 Canal", message.channel.mention, True),
                ("🔗 Link detectado", f"||{urls[0][:100]}||", False),
                ("⚠️ Warn", f"{warn_count}/5", True),
            ]
        )
        await message.channel.send(embed=alert_embed, delete_after=10)

        # DM COMPLETO al usuario con toda la información
        try:
            dm_embed = create_embed(
                "🔗 LINK BLOQUEADO",
                f"Tu mensaje fue eliminado en **{message.guild.name}**",
                color=0xFF0000,
                fields=[
                    ("📍 Canal", f"#{message.channel.name}", True),
                    ("🔗 Link detectado", f"||{urls[0][:200]}||", False),
                    ("📝 Tu mensaje", message.content[:500] if message.content else "*Sin contenido*", False),
                    ("⚠️ Total warns", f"{warn_count}/5", True),
                    ("📋 Razón", "Los links están prohibidos en este servidor", False),
                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                    ("🛡️ Bot", f"**{BOT_NAME}** — Protección activa", False),
                ]
            )
            await message.author.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Log
        await self._log_security(message.guild, "link_blocked", message.author.id,
                                 moderator_id=self.bot.user.id,
                                 details=f"Link: {urls[0][:100]}")

        return True

    async def _check_phishing(self, message):
        """Sistema anti-phishing avanzado"""
        content = message.content.lower()
        urls = re.findall(r'https?://[^\s]+', content)

        for url in urls:
            for domain in PHISHING_DOMAINS:
                if domain.lower() in url.lower():
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass

                    from database.db import add_warn, get_warn_count
                    await add_warn(message.guild.id, message.author.id, self.bot.user.id,
                                   f"Phishing detectado: {url}")
                    warn_count = await get_warn_count(message.guild.id, message.author.id)

                    # Embed en canal
                    embed = phishing_detected(message.author, url)
                    await message.channel.send(embed=embed, delete_after=10)

                    # DM COMPLETO
                    try:
                        dm_embed = create_embed(
                            "🎣 PHISHING DETECTADO",
                            f"Tu mensaje contenía un link de phishing en **{message.guild.name}**",
                            color=0xFF0000,
                            fields=[
                                ("🔗 Link malicioso", f"||{url}||", False),
                                ("📝 Tu mensaje", message.content[:500], False),
                                ("⚠️ Total warns", f"{warn_count}/5", True),
                                ("📋 Razón", "Phishing detectado — intento de robo de credenciales", False),
                                ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                                ("🛡️ Bot", f"**{BOT_NAME}** — Protección anti-phishing activa", False),
                            ]
                        )
                        await message.author.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass

                    await self._log_security(message.guild, "phishing_detect", message.author.id,
                                             moderator_id=self.bot.user.id,
                                             details=f"Phishing URL: {url}")
                    return True
        return False

    async def _check_nsfw(self, message):
        """Detecta contenido NSFW en mensajes e imágenes"""
        content = message.content.lower()
        has_nsfw_content = False
        reason = ""

        # Verificar texto
        for keyword in NSFW_KEYWORDS:
            if keyword in content:
                has_nsfw_content = True
                reason = f"Texto NSFW detectado: '{keyword}'"
                break

        # Verificar attachments (imágenes)
        if not has_nsfw_content:
            for attachment in message.attachments:
                if attachment.content_type:
                    content_type = attachment.content_type.lower()
                    # Detectar imágenes NSFW
                    if any(t in content_type for t in ['image/', 'video/']):
                        # Verificar nombre de archivo
                        filename = attachment.filename.lower()
                        nsfw_extensions = ['nsfw', 'porn', 'xxx', 'nude', 'hentai']
                        for ext in nsfw_extensions:
                            if ext in filename:
                                has_nsfw_content = True
                                reason = f"Archivo NSFW detectado: {attachment.filename}"
                                break

        if not has_nsfw_content:
            return False

        # Eliminar el mensaje
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        # Warn + Ban automático por NSFW
        from database.db import add_warn, get_warn_count
        await add_warn(message.guild.id, message.author.id, self.bot.user.id, reason)
        warn_count = await get_warn_count(message.guild.id, message.author.id)

        # Ban automático por contenido NSFW
        try:
            await message.author.ban(reason=f"NSFW detectado: {reason}")

            # DM al usuario baneado
            try:
                dm_embed = create_embed(
                    "🚫 BAN POR CONTENIDO NSFW",
                    f"Fuiste baneado de **{message.guild.name}** por contenido NSFW.",
                    color=0xFF0000,
                    fields=[
                        ("📝 Razón", reason, False),
                        ("⚠️ Total warns", f"{warn_count}", True),
                        ("📋 Tipo", "Contenido NSFW/Pornográfico", True),
                        ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                        ("🛡️ Bot", f"**{BOT_NAME}** — Protección anti-NSFW activa", False),
                    ]
                )
                await message.author.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            # Si no puede banear, al menos mutear
            try:
                timeout_until = discord.utils.utcnow() + timedelta(hours=24)
                await message.author.timeout(timeout_until, reason=f"NSFW detectado: {reason}")
            except discord.Forbidden:
                pass

        # Embed de alerta
        alert_embed = create_embed(
            "🚫 CONTENIDO NSFW BLOQUEADO",
            f"**{message.author.mention}** fue baneado por contenido NSFW",
            color=0xFF0000,
            fields=[
                ("📝 Razón", reason, False),
                ("🔨 Acción", "Ban automático", True),
            ]
        )
        await message.channel.send(embed=alert_embed, delete_after=10)

        await self._log_security(message.guild, "nsfw_ban", message.author.id,
                                 moderator_id=self.bot.user.id,
                                 details=reason)
        return True

    async def _handle_unauthorized_bot(self, member):
        """Banea bots no autorizados y al usuario que los invitó"""
        guild = member.guild

        # Buscar quién invitó al bot
        inviter = None
        try:
            async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    inviter = entry.user
                    break
        except discord.Forbidden:
            pass

        # Banear al bot
        try:
            await member.ban(reason="Auto-ban: bot no autorizado")
        except discord.Forbidden:
            pass

        # DM al bot (por si tiene soporte de DMs)
        try:
            dm_embed = create_embed(
                "🤖 BOT BANEADO",
                f"Fuiste baneado de **{guild.name}** por ser un bot no autorizado.",
                color=0xFF0000,
                fields=[
                    ("📋 Razón", "Los bots deben ser autorizados por un admin", False),
                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                ]
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Si hay inviter, también expulsarlo
        if inviter and not inviter.bot:
            try:
                # DM al inviter
                dm_embed = create_embed(
                    "👢 EXPULSADO POR INVITAR BOT NO AUTORIZADO",
                    f"Fuiste expulsado de **{guild.name}** por invitar un bot no autorizado.",
                    color=0xFF0000,
                    fields=[
                        ("🤖 Bot baneado", str(member), True),
                        ("📝 Razón", "Los bots no autorizados están prohibidos", False),
                        ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                    ]
                )
                await inviter.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            try:
                await inviter.kick(reason=f"Invitó bot no autorizado: {member.name}")
            except discord.Forbidden:
                pass

        await self._log_security(
            guild, "unauthorized_bot", member.id,
            inviter.id if inviter else None,
            details=f"Bot baneado: {member.name} | Invitado por: {inviter if inviter else 'Desconocido'}"
        )

    # ═══════════════════════════════════════════
    #  ANTI-FLOOD (Mensajes Rápidos)
    # ═══════════════════════════════════════════

    async def _check_flood(self, message):
        """
        Anti-Flood: Si un usuario envía más de 4 mensajes en 3 segundos
        → Elimina todos los mensajes + DM con embed de advertencia
        """
        user_id = message.author.id
        now = time.time()

        self.flood_tracker[user_id].append(now)
        self.flood_tracker[user_id] = [
            t for t in self.flood_tracker[user_id]
            if now - t < FLOOD_TIME_WINDOW
        ]

        msg_count = len(self.flood_tracker[user_id])

        if msg_count >= FLOOD_THRESHOLD:
            # Incrementar infracciones
            self.infraction_count[user_id] += 1
            repeat = self.infraction_count[user_id]

            # Acción según configuración
            settings = await db.get_guild_settings(message.guild.id)
            mute_duration = settings.get('mute_duration', FLOOD_MUTE_DURATION) if settings else FLOOD_MUTE_DURATION

            # Determinar acción
            if AGGRESSIVE_MODE and repeat >= AGGRESSIVE_MAX_WARNINGS_BAN:
                # BAN automático por reincidencia
                try:
                    dm_embed = create_embed(
                        "🔨 BAN POR FLOOD REITERADO",
                        f"Fuiste baneado de **{message.guild.name}** por flood reiterado.",
                        color=0xFF0000,
                        fields=[
                            ("📝 Razón", f"Flood reiterado ({repeat} veces)", False),
                            ("🔢 Infracciones", str(repeat), True),
                            ("⚠️ Límite", str(AGGRESSIVE_MAX_WARNINGS_BAN), True),
                            ("🕐 Hora", f"<t:{int(now)}:F>", True),
                            ("🛡️ Bot", f"**{BOT_NAME}** — Modo Agresivo Activo", False),
                        ]
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                try:
                    await message.author.ban(
                        reason=f"Flood reiterado ({repeat} veces) — Modo Agresivo"
                    )
                except discord.Forbidden:
                    pass

                await self._log_security(
                    message.guild, "flood_ban", message.author.id,
                    self.bot.user.id,
                    details=f"Ban por flood reiterado ({repeat} veces)"
                )
                self.flood_tracker[user_id] = []
                return True

            elif FLOOD_ACTION == "mute" or (AGGRESSIVE_MODE and repeat >= 2):
                # Mute temporal
                timeout_until = discord.utils.utcnow() + timedelta(seconds=mute_duration)
                try:
                    await message.author.timeout(
                        timeout_until,
                        reason=f"Anti-Flood: {msg_count} mensajes en {FLOOD_TIME_WINDOW}s"
                    )
                except discord.Forbidden:
                    pass

                # DM al usuario con info COMPLETA
                try:
                    dm_embed = create_embed(
                        "🚫 FLOOD DETECTADO",
                        f"Fuiste silenciado en **{message.guild.name}** por enviar demasiados mensajes rápidamente.",
                        color=0xFF4500,
                        fields=[
                            ("📝 Razón", f"{msg_count} mensajes en {FLOOD_TIME_WINDOW} segundos", False),
                            ("🔇 Duración", f"{mute_duration // 60} minutos", True),
                            ("🔢 Infracciones", str(repeat), True),
                            ("⚠️ Siguiente acción", "Ban automático" if AGGRESSIVE_BAN_ON_REPEAT else "Mute más largo", True),
                            ("🕐 Hora", f"<t:{int(now)}:F>", True),
                            ("🛡️ Bot", f"**{BOT_NAME}** — Protección Anti-Flood", False),
                        ]
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                await self._log_security(
                    message.guild, "flood_mute", message.author.id,
                    self.bot.user.id,
                    details=f"Mute por flood: {msg_count} msgs en {FLOOD_TIME_WINDOW}s (infracción #{repeat})"
                )
                self.flood_tracker[user_id] = []
                return True

            elif FLOOD_ACTION == "kick" or (AGGRESSIVE_MODE and repeat >= 3):
                # Kick
                try:
                    dm_embed = create_embed(
                        "👢 KICK POR FLOOD",
                        f"Fuiste expulsado de **{message.guild.name}** por flood.",
                        color=0xFF4500,
                        fields=[
                            ("📝 Razón", f"Flood reiterado ({repeat} veces)", False),
                            ("🔢 Infracciones", str(repeat), True),
                            ("🕐 Hora", f"<t:{int(now)}:F>", True),
                        ]
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass
                try:
                    await message.author.kick(reason=f"Flood reiterado ({repeat} veces)")
                except discord.Forbidden:
                    pass
                self.flood_tracker[user_id] = []
                return True

            else:
                # WARN por flood
                from database.db import add_warn, get_warn_count
                await add_warn(
                    message.guild.id, message.author.id,
                    self.bot.user.id,
                    f"Flood: {msg_count} mensajes en {FLOOD_TIME_WINDOW}s"
                )
                warn_count = await get_warn_count(message.guild.id, message.author.id)

                # DM al usuario con embed completo
                try:
                    dm_embed = create_embed(
                        "⚡ FLOOD DETECTADO",
                        f"Tu mensaje fue eliminado en **{message.guild.name}** por flood.",
                        color=0xFFFF00,
                        fields=[
                            ("📍 Canal", f"#{message.channel.name}", True),
                            ("📝 Tu mensaje", message.content[:500] if message.content else "*Sin contenido*", False),
                            ("⚡ Mensajes rápidos", f"{msg_count} en {FLOOD_TIME_WINDOW}s", True),
                            ("⚠️ Total warns", f"{warn_count}/5", True),
                            ("📋 Razón", "Envío demasiados mensajes en poco tiempo", False),
                            ("🕐 Hora", f"<t:{int(now)}:F>", True),
                            ("🛡️ Bot", f"**{BOT_NAME}** — Anti-Flood Activo", False),
                        ]
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                await self._log_security(
                    message.guild, "flood_warn", message.author.id,
                    self.bot.user.id,
                    details=f"Warn por flood: {msg_count} msgs en {FLOOD_TIME_WINDOW}s (warn #{warn_count})"
                )
                self.flood_tracker[user_id] = []
                return True

        return False

    # ═══════════════════════════════════════════
    #  ANTI-MENCIÓN (4+ menciones)
    # ═══════════════════════════════════════════

    async def _check_mentions(self, message):
        """
        Anti-Mención: Si un usuario menciona a más de 4 personas
        → Eliminar mensaje + DM con embed de advertencia
        """
        mention_count = len(message.mentions) + len(message.role_mentions)

        if mention_count <= MAX_MENTION_COUNT:
            return False

        # Eliminar el mensaje
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        # Warn al usuario
        from database.db import add_warn, get_warn_count
        await add_warn(
            message.guild.id, message.author.id,
            self.bot.user.id,
            f"Menciones excesivas: {mention_count} menciones en un mensaje"
        )
        warn_count = await get_warn_count(message.guild.id, message.author.id)

        # Lista de mencionados
        mentioned = []
        for u in message.mentions[:10]:
            mentioned.append(f"• {u.mention}")
        for r in message.role_mentions[:5]:
            mentioned.append(f"• {r.mention}")

        # Embed en el canal
        alert_embed = create_embed(
            "📢 MENCIONES EXCESIVAS",
            f"**{message.author.mention}** mencionó a demasiadas personas",
            color=0xFF0000,
            fields=[
                ("📢 Menciones", str(mention_count), True),
                ("⚠️ Warn", f"{warn_count}/5", True),
            ]
        )
        await message.channel.send(embed=alert_embed, delete_after=10)

        # DM COMPLETO al usuario con toda la info
        try:
            dm_embed = create_embed(
                "📢 MENCIONES EXCESIVAS",
                f"Tu mensaje fue eliminado en **{message.guild.name}** por menciones excesivas.",
                color=0xFF0000,
                fields=[
                    ("📍 Canal", f"#{message.channel.name}", True),
                    ("📝 Tu mensaje", message.content[:500] if message.content else "*Sin contenido*", False),
                    ("📢 Menciones realizadas", str(mention_count), True),
                    ("👤 Mencionados\n(primeros 10)", "\n".join(mentioned) if mentioned else "N/A", False),
                    ("⚠️ Total warns", f"{warn_count}/5", True),
                    ("📋 Razón", f"Mencionaste a {mention_count} personas/menciones en un solo mensaje", False),
                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                    ("🛡️ Bot", f"**{BOT_NAME}** — Anti-Mención Activo", False),
                ]
            )
            await message.author.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await self._log_security(
            message.guild, "mention_spam", message.author.id,
            self.bot.user.id,
            details=f"Menciones excesivas: {mention_count} menciones en #{message.channel.name}"
        )

        return True

    # ═══════════════════════════════════════════
    #  DETECCIÓN DE CUENTAS ALT (Nuevas)
    # ═══════════════════════════════════════════

    async def _check_alt_account(self, member):
        """
        Detecta cuentas nuevas como posibles alternativas
        Si la cuenta tiene menos de ALT_ACCOUNT_DAYS días → alerta
        """
        if not AGGRESSIVE_ANTI_ALT_ACCOUNTS:
            return False

        account_age = (datetime.utcnow() - member.created_at).days

        if account_age < ALT_ACCOUNT_DAYS:
            settings = await db.get_guild_settings(member.guild.id)
            log_channel_id = settings.get('log_channel_id') if settings else None

            if log_channel_id:
                channel = member.guild.get_channel(log_channel_id)
                if channel:
                    embed = create_embed(
                        "🔍 CUENTA NUEVA / POSIBLE ALT",
                        f"**{member.mention}** tiene una cuenta de solo **{account_age} días**",
                        color=0xFF4500,
                        fields=[
                            ("👤 Usuario", f"{member}\n`{member.id}`", True),
                            ("📅 Cuenta creada", f"Hace {account_age} días", True),
                            ("⚠️ Riesgo", "ALTA — Posible cuenta alternativa", True),
                            ("🛡️ Bot", f"**{BOT_NAME}** — Detección de Alts", False),
                        ]
                    )
                    await channel.send(embed=embed)

            # Log
            await self._log_security(
                member.guild, "alt_account_detected", member.id,
                details=f"Cuenta de {account_age} días — posible alt account"
            )
            return True

        return False

    async def _check_auto_mod(self, message, settings):
        """Sistema de auto-moderación avanzado"""
        content = message.content

        # Verificar menciones excesivas
        if len(message.mentions) > MAX_MENTIONS:
            try:
                await message.delete()
                await message.channel.send(
                    embed=security_alert("Menciones excesivas",
                                        f"{message.author.mention} hizo demasiadas menciones",
                                        "medium"),
                    delete_after=10
                )
                return
            except discord.Forbidden:
                pass

        # Verificar mayúsculas excesivas
        if len(content) > MIN_CAPS_LENGTH:
            caps_count = sum(1 for c in content if c.isupper())
            caps_percent = (caps_count / len(content)) * 100
            if caps_percent > MAX_CAPS_PERCENT:
                try:
                    await message.delete()
                    await message.channel.send(
                        embed=security_alert("Exceso de mayúsculas",
                                            f"{message.author.mention} uso demasiadas mayúsculas",
                                            "low"),
                        delete_after=10
                    )
                    return
                except discord.Forbidden:
                    pass

        # Verificar palabras prohibidas
        content_lower = content.lower()
        for word in BANNED_WORDS:
            if word in content_lower:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass

                from database.db import add_warn, get_warn_count
                await add_warn(message.guild.id, message.author.id, self.bot.user.id,
                               f"Palabra prohibida: {word}")
                warn_count = await get_warn_count(message.guild.id, message.author.id)

                # DM al usuario
                try:
                    dm_embed = create_embed(
                        "🚫 PALABRA PROHIBIDA",
                        f"Tu mensaje fue eliminado en **{message.guild.name}**",
                        color=0xFF0000,
                        fields=[
                            ("📍 Canal", f"#{message.channel.name}", True),
                            ("📝 Tu mensaje", message.content[:500], False),
                            ("⚠️ Total warns", f"{warn_count}/5", True),
                            ("📋 Razón", f"Palabra prohibida detectada", False),
                            ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                        ]
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                await self._log_security(message.guild, "banned_word", message.author.id,
                                         moderator_id=self.bot.user.id,
                                         details=f"Palabra: {word}")
                return

        # Verificar emojis excesivos
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        emoji_count = len(emoji_pattern.findall(content))
        if emoji_count > MAX_EMOJI_COUNT:
            try:
                await message.delete()
                await message.channel.send(
                    embed=security_alert("Exceso de emojis",
                                        f"{message.author.mention} envio demasiados emojis",
                                        "low"),
                    delete_after=10
                )
                return
            except discord.Forbidden:
                pass

    # ═══════════════════════════════════════════
    #  COMANDOS DE SEGURIDAD
    # ═══════════════════════════════════════════

    @app_commands.command(name="security", description="Estado de seguridad del servidor")
    async def security_status(self, interaction: discord.Interaction):
        """Muestra el estado actual de seguridad"""
        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings:
            await db.update_guild_settings(interaction.guild.id)
            settings = await db.get_guild_settings(interaction.guild.id)

        from utils.embeds import security_status_embed
        embed = security_status_embed(interaction.guild, settings)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="raid", description="Configurar anti-raid")
    @app_commands.describe(threshold="Número de joins para activar", window="Ventana de tiempo en segundos")
    async def config_raid(self, interaction: discord.Interaction, threshold: int = None, window: int = None):
        """Configura el sistema anti-raid"""
        if not await self._check_security_role(interaction):
            return

        updates = {}
        if threshold is not None:
            updates['raid_threshold'] = threshold
        if window is not None:
            updates['raid_window'] = window

        if updates:
            await db.update_guild_settings(interaction.guild.id, **updates)

        settings = await db.get_guild_settings(interaction.guild.id)
        embed = create_embed(
            "🚨 Configuración Anti-Raid",
            "Sistema anti-raid configurado correctamente",
            color=0xFF0000,
            fields=[
                ("👥 Umbral", f"{settings.get('raid_threshold', RAID_JOIN_THRESHOLD)} joins", True),
                ("⏱️ Ventana", f"{settings.get('raid_window', RAID_TIME_WINDOW)} segundos", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="antispam", description="Configurar anti-spam")
    @app_commands.describe(threshold="Mensajes para activar", window="Ventana de tiempo", mute_duration="Duración del mute en segundos")
    async def config_antispam(self, interaction: discord.Interaction,
                              threshold: int = None, window: int = None, mute_duration: int = None):
        """Configura el sistema anti-spam"""
        if not await self._check_security_role(interaction):
            return

        updates = {}
        if threshold is not None:
            updates['spam_threshold'] = threshold
        if window is not None:
            updates['spam_window'] = window
        if mute_duration is not None:
            updates['mute_duration'] = mute_duration

        if updates:
            await db.update_guild_settings(interaction.guild.id, **updates)

        settings = await db.get_guild_settings(interaction.guild.id)
        embed = create_embed(
            "🚫 Configuración Anti-Spam",
            "Sistema anti-spam configurado correctamente",
            color=0xFFFF00,
            fields=[
                ("💬 Umbral", f"{settings.get('spam_threshold', SPAM_MESSAGE_THRESHOLD)} mensajes", True),
                ("⏱️ Ventana", f"{settings.get('spam_window', SPAM_TIME_WINDOW)} segundos", True),
                ("🔇 Mute", f"{settings.get('mute_duration', SPAM_MUTE_DURATION)} segundos", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="blacklist", description="Agregar usuario a la blacklist")
    @app_commands.describe(user="Usuario a blacklistearear", reason="Razón")
    async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        """Agrega un usuario a la blacklist (auto-ban)"""
        if not await self._check_security_role(interaction):
            return

        await db.add_blacklist(interaction.guild.id, user.id, reason, interaction.user.id)

        # DM al usuario
        try:
            dm_embed = create_embed(
                "黑名单 BLACKLIST",
                f"Fuiste agregado a la blacklist de **{interaction.guild.name}**",
                color=0xFF0000,
                fields=[
                    ("📝 Razón", reason, False),
                    ("👮 Agregado por", str(interaction.user), True),
                    ("📋 ID", f"`{user.id}`", True),
                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        try:
            await user.ban(reason=f"Blacklist: {reason}")
        except discord.Forbidden:
            pass

        embed = create_embed(
            "黑名单 BLACKLIST",
            f"**{user.mention}** ha sido agregado a la blacklist y baneado",
            color=0xFF0000,
            fields=[
                ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
                ("📝 Razón", reason, True),
                ("👮 Agregado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unblacklist", description="Remover usuario de la blacklist")
    @app_commands.describe(user_id="ID del usuario a remover")
    async def unblacklist_user(self, interaction: discord.Interaction, user_id: str):
        """Remueve un usuario de la blacklist"""
        if not await self._check_security_role(interaction):
            return

        uid = int(user_id)
        await db.remove_blacklist(interaction.guild.id, uid)

        embed = create_embed(
            "✅ BLACKLIST REMOVIDA",
            f"Usuario `{uid}` removido de la blacklist",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="whitelist", description="Agregar usuario a la whitelist (inmune a todo)")
    @app_commands.describe(user="Usuario a whitelistear")
    async def whitelist_user(self, interaction: discord.Interaction, user: discord.Member):
        """Agrega un usuario a la whitelist (inmune a todo el auto-mod)"""
        if not await self._check_security_role(interaction):
            return

        await db.add_whitelist(interaction.guild.id, user.id, interaction.user.id)

        embed = create_embed(
            "✅ WHITELIST — USUARIO INMUNE",
            f"**{user.mention}** ahora es **INMUNE** a todo el sistema de auto-mod",
            color=0x00FF00,
            fields=[
                ("👤 Usuario", user.mention, True),
                ("🛡️ Estado", "INMUNE A TODO", True),
                ("📝 Incluye", "Anti-spam, anti-links, anti-NSFW, auto-mod, palabras prohibidas", False),
                ("👑 Agregado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unwhitelist", description="Remover usuario de la whitelist")
    @app_commands.describe(user_id="ID del usuario a remover")
    async def unwhitelist_user(self, interaction: discord.Interaction, user_id: str):
        """Remueve un usuario de la whitelist (ya no será inmune)"""
        if not await self._check_security_role(interaction):
            return

        uid = int(user_id)
        await db.remove_whitelist(interaction.guild.id, uid)

        embed = create_embed(
            "✅ WHITELIST REMOVIDA",
            f"Usuario `{uid}` ya **NO** es inmune al auto-mod",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wl", description="Ver whitelist completa")
    async def view_whitelist(self, interaction: discord.Interaction):
        """Muestra todos los usuarios en la whitelist"""
        if not await self._check_security_role(interaction):
            return

        wl = await db.get_whitelist(interaction.guild.id)
        if not wl:
            embed = create_embed("✅ Whitelist", "No hay usuarios en la whitelist.", color=0x00FF00)
            await interaction.response.send_message(embed=embed)
            return

        lines = []
        for entry in wl:
            member = interaction.guild.get_member(entry[2])
            name = member.mention if member else f"`{entry[2]}`"
            lines.append(f"• {name}")

        embed = create_embed(
            "✅ Whitelist (Inmunes)",
            "\n".join(lines[:20]),
            color=0x00FF00,
            fields=[("👥 Total", str(len(wl)), True)]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    async def _check_security_role(self, interaction):
        """Verifica si el usuario tiene un rol de seguridad"""
        has_role = any(role.name in SECURITY_ROLES for role in interaction.user.roles)
        if not has_role:
            embed = create_embed(
                "❌ Sin permisos",
                "No tienes los permisos necesarios para este comando.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def _log_security(self, guild, event_type, user_id=None, moderator_id=None, details=None):
        """Registra un evento de seguridad"""
        await db.add_log(guild.id, event_type, user_id, moderator_id, details)

        settings = await db.get_guild_settings(guild.id)
        if not settings or not settings.get('logs_enabled', True):
            return

        log_channel_id = settings.get('log_channel_id')
        if not log_channel_id:
            return

        channel = guild.get_channel(log_channel_id)
        if not channel:
            return

        event_names = {
            "member_join": "📥 Miembro nuevo",
            "member_leave": "📤 Miembro salió",
            "message_delete": "🗑️ Mensaje eliminado",
            "message_edit": "✏️ Mensaje editado",
            "voice_state": "🔊 Cambio de voz",
            "spam_mute": "🔇 Mute por spam",
            "phishing_detect": "🎣 Phishing detectado",
            "raid_ban": "🚨 Ban por raid",
            "blacklist_ban": "黑名单 Blacklist ban",
            "link_blocked": "🔗 Link bloqueado",
            "nsfw_ban": "🚫 Ban por NSFW",
            "unauthorized_bot": "🤖 Bot no autorizado baneado",
            "banned_word": "🚫 Palabra prohibida",
            "flood_warn": "⚡ Warn por flood",
            "flood_mute": "🔇 Mute por flood",
            "flood_ban": "🔨 Ban por flood",
            "mention_spam": "📢 Spam de menciones",
            "alt_account_detected": "🔍 Cuenta alt detectada",
            "admin_channel_delete": "⚠️ Admin eliminó canal",
            "admin_channel_update": "⚠️ Admin editó canal",
            "admin_ban": "🔨 Admin baneó usuario",
            "admin_unban": "✅ Admin desbaneó usuario",
        }

        title = event_names.get(event_type, f"📋 {event_type}")
        user_mention = f"<@{user_id}>" if user_id else "N/A"
        mod_mention = f"<@{moderator_id}>" if moderator_id else "AutoMod"

        color = 0xFF0000
        if "ban" in event_type or "raid" in event_type or "nsfw" in event_type:
            color = 0xFF0000
        elif "admin" in event_type:
            color = 0xFF4500
        else:
            color = 0x00BFFF

        embed = create_embed(
            title,
            f"**Usuario:** {user_mention}\n**Moderador:** {mod_mention}",
            color=color,
            fields=[
                ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:R>", True),
                ("📋 Evento", event_type, True),
            ]
        )

        if details:
            embed.add_field(name="📝 Detalles", value=details[:1024], inline=False)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    async def _log_and_dm(self, guild, event_type, user, details):
        """Log de seguridad + DM al usuario"""
        await self._log_security(guild, event_type, user.id, details=details)

        try:
            dm_embed = create_embed(
                "🚨 ACCIÓN DE SEGURIDAD",
                f"Se tomó una acción en **{guild.name}**",
                color=0xFF0000,
                fields=[
                    ("📝 Razón", details, False),
                    ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(SecurityCog(bot))
