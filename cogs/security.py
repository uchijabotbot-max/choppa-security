"""
cogs/security.py - Motor de Seguridad v6
Anti-Raid, Anti-Spam, Anti-Flood, Anti-Links, Anti-Phishing
Anti-NSFW, Anti-Bots, Anti-Extension, Auto-Mod, Deteccion de Alts
"""
import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
import time
import re
from datetime import datetime, timedelta

from config import (
    RAID_JOIN_THRESHOLD, RAID_TIME_WINDOW, SPAM_THRESHOLD, SPAM_TIME_WINDOW,
    MUTE_DEFAULT_DURATION, MAX_MENTIONS, MAX_CAPS_PERCENT, MIN_CAPS_LENGTH,
    MAX_EMOJI_COUNT, BANNED_WORDS, BANNED_WORDS_BAN, BAD_WORD_BAN_THRESHOLD,
    PHISHING_DOMAINS, SECURITY_ROLES,
    BLOCK_ALL_LINKS, NSFW_KEYWORDS, FLOOD_THRESHOLD, FLOOD_TIME_WINDOW,
    SUSPICIOUS_NAMES, ALT_ACCOUNT_DAYS, BOT_NAME,
    ANTI_INVITE_ENABLED, INVITE_PATTERNS,
    ANTI_ROLE_DELETE_ENABLED, ROLE_DELETE_THRESHOLD, ROLE_DELETE_TIME_WINDOW,
    ANTI_MASS_KICK_ENABLED, MASS_KICK_THRESHOLD, MASS_KICK_TIME_WINDOW,
    ANTI_MASS_BAN_ENABLED, MASS_BAN_THRESHOLD, MASS_BAN_TIME_WINDOW,
    COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_ORANGE
)
from utils.embeds import (
    create_embed, raid_detected, spam_detected, link_blocked,
    phishing_detected, nsfw_detected, flood_detected, mention_spam,
    unauthorized_bot, security_status
)
from database import db


class Security(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.join_times = defaultdict(list)
        self.msg_times = defaultdict(list)
        self.flood_tracker = defaultdict(list)
        self.raid_cooldown = {}
        self.link_pattern = re.compile(
            r'https?://[^\s]+|www\.[^\s]+|discord\.gg/[a-zA-Z0-9]+|discord\.com/invite/[a-zA-Z0-9]+',
            re.IGNORECASE
        )

    # ==========================================
    #  EVENTOS
    # ==========================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = await db.get_settings(guild.id) or {}
        await db.ensure_settings(guild.id)

        if member.bot:
            await self._handle_bot(member)
            return

        if settings.get("anti_raid", True):
            await self._check_raid(member)

        account_age = (datetime.utcnow() - member.created_at).days
        if account_age < ALT_ACCOUNT_DAYS:
            await self._alert_log(guild, "🔍 CUENTA NUEVA",
                member.mention + " tiene una cuenta de solo **" + str(account_age) + " dias** (posible alt)",
                COLOR_ORANGE)

        if await db.is_blacklisted(guild.id, member.id):
            try:
                await member.ban(reason="Auto-ban: en blacklist")
                await self._log(guild, "blacklist_ban", member.id, details="En blacklist")
            except discord.Forbidden:
                pass

        if member.name.lower() in SUSPICIOUS_NAMES or member.display_name.lower() in SUSPICIOUS_NAMES:
            await self._alert_log(guild, "🔍 NOMBRE SOSPECHOSO",
                member.mention + " tiene un nombre sospechoso: `" + member.name + "`",
                COLOR_ORANGE)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        settings = await db.get_settings(guild_id) or {}

        if await db.is_whitelisted(guild_id, user_id):
            return

        if settings.get("anti_spam", True):
            if await self._check_flood(message, settings):
                return

        if settings.get("anti_spam", True):
            if await self._check_spam(message, settings):
                return

        if settings.get("auto_mod", True):
            if await self._check_mentions(message):
                return

        if BLOCK_ALL_LINKS:
            if await self._check_links(message):
                return

        # Anti-Invite
        if ANTI_INVITE_ENABLED:
            if await self._check_invite(message):
                return

        if settings.get("anti_phishing", True):
            if await self._check_phishing(message):
                return

        if await self._check_nsfw(message):
            return

        if settings.get("auto_mod", True):
            await self._check_automod(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        await self._log(message.guild, "message_delete", message.author.id,
                        details="Canal: " + message.channel.mention)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        action = ""
        if before.channel is None and after.channel:
            action = "Conectado a " + after.channel.name
        elif before.channel and after.channel is None:
            action = "Desconectado de " + before.channel.name
        if action:
            await self._log(member.guild, "voice_state", member.id, details=action)

    # ==========================================
    #  ANTI-EXTENSION / ANTI-APLICACION
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        guild = after
        if before.premium_tier != after.premium_tier:
            await self._alert_log(guild, "🚀 BOOST CAMBIADO",
                "Nivel de boost cambiado de " + str(before.premium_tier) + " a " + str(after.premium_tier),
                COLOR_BLUE)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                if not entry.user.bot:
                    ch_name = channel.name
                    await self._alert_log(guild, "🔗 WEBHOOK CREADO",
                        entry.user.mention + " creo un webhook en **" + ch_name + "**\nLos webhooks son monitoreados por seguridad",
                        COLOR_RED)
                    await self._log(guild, "webhook_create", entry.user.id, details="Canal: " + ch_name)
                    try:
                        dm = create_embed("🔗 WEBHOOK CREADO",
                            "Creaste un webhook en **" + ch_name + "** en **" + guild.name + "**",
                            COLOR_YELLOW,
                            [("📍 Canal", channel.mention, True),
                             ("⚠️ Nota", "Los webhooks son monitoreados por seguridad", False)])
                        await entry.user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        guild = role.guild
        dangerous_perms = [
            "administrator", "ban_members", "kick_members",
            "manage_guild", "manage_channels", "manage_roles",
            "manage_webhooks", "manage_emojis",
        ]
        found = []
        for perm_name, perm_value in role.permissions:
            if perm_name in dangerous_perms and perm_value:
                found.append(perm_name)
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id and not entry.user.bot:
                    role_name = role.name
                    if found:
                        perm_str = ", ".join(found)
                        await self._alert_log(guild, "🎭 ROL PELIGROSO CREADO",
                            entry.user.mention + " creo el rol **" + role_name + "** con permisos peligrosos: " + perm_str,
                            COLOR_RED)
                        try:
                            await role.delete(reason="Rol con permisos peligrosos bloqueados")
                            try:
                                dm = create_embed("🎭 ROL ELIMINADO",
                                    "El rol **" + role_name + "** fue eliminado por permisos peligrosos",
                                    COLOR_RED,
                                    [("⚠️ Permisos", perm_str, False),
                                     ("📍 Guild", guild.name, True)])
                                await entry.user.send(embed=dm)
                            except discord.Forbidden:
                                pass
                        except discord.Forbidden:
                            pass
                    else:
                        await self._alert_log(guild, "🎭 ROL CREADO",
                            entry.user.mention + " creo el rol **" + role_name + "**",
                            COLOR_YELLOW)
                    perm_detail = ", ".join(found) if found else "Ninguno"
                    await self._log(guild, "role_create", entry.user.id,
                                    details="Rol: " + role_name + " | Peligrosos: " + perm_detail)
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        if added:
            if len(added) >= 5:
                try:
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.emoji_create):
                        if not entry.user.bot:
                            count = len(added)
                            await self._alert_log(guild, "😀 SPAM DE EMOJIS",
                                entry.user.mention + " agrego " + str(count) + " emojis de una vez",
                                COLOR_RED)
                            await self._log(guild, "emoji_spam", entry.user.id,
                                            details=str(count) + " emojis agregados")
                            return
                except discord.Forbidden:
                    pass
            count_added = len(added)
            await self._alert_log(guild, "😀 EMOJIS AGREGADOS",
                "Se agregaron **" + str(count_added) + "** emojis nuevos",
                COLOR_YELLOW)

    # ==========================================
    #  ANTI-INVITE (bloquear invitaciones)
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not ANTI_ROLE_DELETE_ENABLED:
            return
        guild = role.guild
        now = time.time()
        # Track role deletes
        if not hasattr(self, '_role_delete_times'):
            self._role_delete_times = defaultdict(list)
        self._role_delete_times[guild.id].append(now)
        self._role_delete_times[guild.id] = [
            t for t in self._role_delete_times[guild.id]
            if now - t < ROLE_DELETE_TIME_WINDOW
        ]
        if len(self._role_delete_times[guild.id]) >= ROLE_DELETE_THRESHOLD:
            # Nuke detectado - buscar al responsable
            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.role_delete):
                    if not entry.user.bot:
                        user = entry.user
                        try:
                            dm = create_embed("🔨 BAN - MASS ROLE DELETE",
                                "Fuiste baneado de **" + guild.name + "** por eliminar multiples roles",
                                COLOR_RED,
                                [("📝 Razon", "Eliminacion masiva de roles", False),
                                 ("🔢 Roles eliminados", str(len(self._role_delete_times[guild.id])), True)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                        try:
                            await user.ban(reason="Mass role delete: " + str(len(self._role_delete_times[guild.id])) + " roles")
                        except discord.Forbidden:
                            pass
                        await self._alert_log(guild, "🔨 BAN - MASS ROLE DELETE",
                            user.mention + " fue baneado por eliminar multiples roles",
                            COLOR_RED)
                        await self._log(guild, "mass_role_delete_ban", user.id,
                                        details=str(len(self._role_delete_times[guild.id])) + " roles eliminados")
                        break
            except discord.Forbidden:
                pass
            self._role_delete_times[guild.id] = []

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.guild:
            return
        guild = member.guild

        # Log member leave
        await self._log(guild, "member_leave", member.id)

        # Anti-Mass Kick
        if ANTI_MASS_KICK_ENABLED:
            now = time.time()
            if not hasattr(self, '_kick_times'):
                self._kick_times = defaultdict(list)
            self._kick_times[guild.id].append(now)
            self._kick_times[guild.id] = [
                t for t in self._kick_times[guild.id]
                if now - t < MASS_KICK_TIME_WINDOW
            ]
            if len(self._kick_times[guild.id]) >= MASS_KICK_THRESHOLD:
                try:
                    async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.kick):
                        if not entry.user.bot:
                            user = entry.user
                            try:
                                dm = create_embed("🔨 BAN - MASS KICK",
                                    "Fuiste baneado de **" + guild.name + "** por expulsar multiples usuarios",
                                    COLOR_RED,
                                    [("📝 Razon", "Expulsion masiva", False),
                                     ("🔢 Usuarios expulsados", str(len(self._kick_times[guild.id])), True)])
                                await user.send(embed=dm)
                            except discord.Forbidden:
                                pass
                            try:
                                await user.ban(reason="Mass kick: " + str(len(self._kick_times[guild.id])) + " kicks")
                            except discord.Forbidden:
                                pass
                            await self._alert_log(guild, "🔨 BAN - MASS KICK",
                                user.mention + " fue baneado por expulsar multiples usuarios",
                                COLOR_RED)
                            await self._log(guild, "mass_kick_ban", user.id,
                                            details=str(len(self._kick_times[guild.id])) + " kicks")
                            break
                except discord.Forbidden:
                    pass
                self._kick_times[guild.id] = []

        # Anti-Mass Ban
        if ANTI_MASS_BAN_ENABLED:
            now = time.time()
            if not hasattr(self, '_ban_times'):
                self._ban_times = defaultdict(list)
            self._ban_times[guild.id].append(now)
            self._ban_times[guild.id] = [
                t for t in self._ban_times[guild.id]
                if now - t < MASS_BAN_TIME_WINDOW
            ]
            if len(self._ban_times[guild.id]) >= MASS_BAN_THRESHOLD:
                try:
                    async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.ban):
                        if not entry.user.bot:
                            user = entry.user
                            try:
                                dm = create_embed("🔨 BAN - MASS BAN",
                                    "Fuiste baneado de **" + guild.name + "** por banear multiples usuarios",
                                    COLOR_RED,
                                    [("📝 Razon", "baneo masivo", False),
                                     ("🔢 Usuarios baneados", str(len(self._ban_times[guild.id])), True)])
                                await user.send(embed=dm)
                            except discord.Forbidden:
                                pass
                            try:
                                await user.ban(reason="Mass ban: " + str(len(self._ban_times[guild.id])) + " bans")
                            except discord.Forbidden:
                                pass
                            await self._alert_log(guild, "🔨 BAN - MASS BAN",
                                user.mention + " fue baneado por banear multiples usuarios",
                                COLOR_RED)
                            await self._log(guild, "mass_ban_ban", user.id,
                                            details=str(len(self._ban_times[guild.id])) + " bans")
                            break
                except discord.Forbidden:
                    pass
                self._ban_times[guild.id] = []

    # ==========================================
    #  MONITOREO DE ADMINS
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id and not entry.user.bot:
                    ch_name = channel.name
                    user = entry.user

                    # BAN INMEDIATO al admin que borra un canal
                    try:
                        dm = create_embed("🔨 BAN - CANAL ELIMINADO",
                            "Fuiste baneado de **" + guild.name + "** por eliminar el canal **" + ch_name + "**",
                            COLOR_RED,
                            [("📍 Canal eliminado", ch_name, True),
                             ("📋 ID del canal", str(channel.id), True),
                             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
                             ("📋 Razon", "Eliminar canales no esta permitido", False)])
                        await user.send(embed=dm)
                    except discord.Forbidden:
                        pass

                    try:
                        await user.ban(reason="Elimino el canal: " + ch_name)
                    except discord.Forbidden:
                        pass

                    await self._alert_log(guild, "🔨 ADMIN BANEADO - CANAL ELIMINADO",
                        user.mention + " fue **BANEADO** por eliminar el canal **" + ch_name + "**",
                        COLOR_RED)
                    await self._log(guild, "admin_ban_channel_delete", user.id,
                                    details="Canal eliminado: " + ch_name)
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append("Nombre: " + before.name + " -> " + after.name)
        if before.topic != after.topic:
            changes.append("Tema modificado")
        if not changes:
            return

        guild = before.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id and not entry.user.bot:
                    changes_str = "\n".join(changes)
                    user = entry.user

                    # Si se modificaron permisos = BAN
                    perm_change = any("permisos" in c.lower() or "permisos" in c.lower() for c in changes)
                    name_change = any("nombre" in c.lower() for c in changes)

                    if perm_change:
                        # BAN por modificar permisos de canal
                        try:
                            dm = create_embed("🔨 BAN - PERMISOS MODIFICADOS",
                                "Fuiste baneado de **" + guild.name + "** por modificar permisos del canal **" + after.name + "**",
                                COLOR_RED,
                                [("📍 Canal", after.name, True),
                                 ("📝 Cambios", changes_str, False),
                                 ("📋 Razon", "Modificar permisos no esta permitido", False)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                        try:
                            await user.ban(reason="Modifico permisos del canal: " + after.name)
                        except discord.Forbidden:
                            pass
                        await self._alert_log(guild, "🔨 ADMIN BANEADO - PERMISOS",
                            user.mention + " fue **BANEADO** por modificar permisos de **" + after.name + "**",
                            COLOR_RED)
                        await self._log(guild, "admin_ban_channel_perms", user.id,
                                        details="Canal: " + after.name + " | Cambios: " + changes_str)
                    elif name_change:
                        # Solo log para cambio de nombre
                        try:
                            dm = create_embed("✏️ CANAL EDITADO",
                                "Editaste **" + after.name + "** en **" + guild.name + "**",
                                COLOR_YELLOW,
                                [("📝 Cambios", changes_str, False)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                        await self._alert_log(guild, "⚠️ CANAL EDITADO",
                            user.mention + " edito **" + after.name + "**\n" + changes_str,
                            COLOR_YELLOW)
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id and not entry.user.bot:
                    reason = entry.reason or "Sin razon"
                    await self._alert_log(guild, "🔨 BAN EJECUTADO",
                        entry.user.mention + " baneo a **" + str(user) + "**\nRazon: " + reason,
                        COLOR_RED)
                    try:
                        dm = create_embed("🔨 HAS SIDO BANEADO",
                            "Fuiste baneado de **" + guild.name + "**",
                            COLOR_RED,
                            [("📝 Razon", reason, False),
                             ("👮 Moderador", str(entry.user), True)])
                        await user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    # ==========================================
    #  MOTOR DE SEGURIDAD
    # ==========================================

    async def _check_raid(self, member):
        gid = member.guild.id
        now = time.time()
        settings = await db.get_settings(gid) or {}
        threshold = settings.get("raid_threshold", RAID_JOIN_THRESHOLD)
        window = RAID_TIME_WINDOW

        self.join_times[gid].append(now)
        self.join_times[gid] = [t for t in self.join_times[gid] if now - t < window]

        if len(self.join_times[gid]) >= threshold:
            if gid in self.raid_cooldown and now - self.raid_cooldown[gid] < 60:
                return
            self.raid_cooldown[gid] = now

            await self._alert_log(member.guild, "🚨 RAID DETECTADO",
                str(len(self.join_times[gid])) + " usuarios se unieron en " + str(RAID_TIME_WINDOW) + " segundos",
                COLOR_RED)

            recent = [
                m for m in member.guild.members
                if m.joined_at and (datetime.utcnow() - m.joined_at).total_seconds() < RAID_TIME_WINDOW
                and not m.bot
            ]
            for m in recent:
                try:
                    dm = create_embed("🚨 BAN POR RAID",
                        "Fuiste baneado de **" + member.guild.name + "** por ser parte de un raid.",
                        COLOR_RED,
                        [("📝 Razon", "Raid: " + str(len(self.join_times[gid])) + " joins en " + str(RAID_TIME_WINDOW) + "s", False)])
                    await m.send(embed=dm)
                except discord.Forbidden:
                    pass
                try:
                    await m.ban(reason="Anti-Raid")
                    await self._log(member.guild, "raid_ban", m.id, details="Auto-ban por raid")
                except discord.Forbidden:
                    pass

            self.join_times[gid] = []

    async def _check_spam(self, message):
        uid = message.author.id
        now = time.time()
        settings = await db.get_settings(message.guild.id) or {}
        threshold = settings.get("spam_threshold", SPAM_THRESHOLD)

        self.msg_times[uid].append(now)
        self.msg_times[uid] = [t for t in self.msg_times[uid] if now - t < SPAM_TIME_WINDOW]

        if len(self.msg_times[uid]) >= threshold:
            duration = settings.get("mute_duration", MUTE_DEFAULT_DURATION)
            until = discord.utils.utcnow() + timedelta(seconds=duration)
            try:
                await message.author.timeout(until, reason="Anti-Spam")
                count = len(self.msg_times[uid])
                await message.channel.send(embed=spam_detected(message.author, count), delete_after=10)
                await self._dm(message.author, "🔇 SILENCIADO POR SPAM",
                    "Fuiste silenciado en **" + message.guild.name + "** por spam.",
                    COLOR_BLUE,
                    [("📝 Razon", str(count) + " mensajes en " + str(SPAM_TIME_WINDOW) + "s", False),
                     ("⏱️ Duracion", str(duration // 60) + " minutos", True)])
                await self._log(message.guild, "spam_mute", uid, details=str(count) + " msgs")
                self.msg_times[uid] = []
                return True
            except discord.Forbidden:
                pass
        return False

    async def _check_flood(self, message, settings):
        uid = message.author.id
        now = time.time()

        self.flood_tracker[uid].append(now)
        self.flood_tracker[uid] = [t for t in self.flood_tracker[uid] if now - t < FLOOD_TIME_WINDOW]

        if len(self.flood_tracker[uid]) >= FLOOD_THRESHOLD:
            count = len(self.flood_tracker[uid])
            await db.add_warn(message.guild.id, uid, self.bot.user.id, "Flood: " + str(count) + " msgs en " + str(FLOOD_TIME_WINDOW) + "s")
            warn_count = await db.get_warn_count(message.guild.id, uid)

            try:
                until = discord.utils.utcnow() + timedelta(seconds=MUTE_DEFAULT_DURATION)
                await message.author.timeout(until, reason="Anti-Flood")
                await message.delete()
                await message.channel.send(embed=flood_detected(message.author, count, FLOOD_TIME_WINDOW), delete_after=10)
                await self._dm(message.author, "⚡ FLOOD DETECTADO",
                    "Fuiste silenciado en **" + message.guild.name + "** por flood.",
                    COLOR_ORANGE,
                    [("📝 Mensajes rapidos", str(count) + " en " + str(FLOOD_TIME_WINDOW) + "s", False),
                     ("⚠️ Warns totales", str(warn_count), True),
                     ("🔇 Duracion", str(MUTE_DEFAULT_DURATION // 60) + " min", True)])
                await self._log(message.guild, "flood_mute", uid, details=str(count) + " msgs en " + str(FLOOD_TIME_WINDOW) + "s")
                self.flood_tracker[uid] = []
                return True
            except discord.Forbidden:
                pass
        return False

    async def _check_mentions(self, message):
        count = len(message.mentions) + len(message.role_mentions)
        if count <= MAX_MENTIONS:
            return False

        await message.delete()
        await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Menciones excesivas: " + str(count))
        warn_count = await db.get_warn_count(message.guild.id, message.author.id)

        await message.channel.send(embed=mention_spam(message.author, count), delete_after=10)
        await self._dm(message.author, "📢 MENCIONES EXCESIVAS",
            "Tu mensaje fue eliminado en **" + message.guild.name + "** por menciones excesivas.",
            COLOR_RED,
            [("📍 Canal", "#" + message.channel.name, True),
             ("📢 Menciones", str(count), True),
             ("⚠️ Warns", str(warn_count), True),
             ("📝 Tu mensaje", message.content[:500], False)])
        await self._log(message.guild, "mention_spam", message.author.id,
                        details=str(count) + " menciones en #" + message.channel.name)
        return True

    async def _check_links(self, message):
        urls = self.link_pattern.findall(message.content)
        if not urls:
            return False

        allowed = ["reglas", "rules", "links", "recursos"]
        if any(ch in message.channel.name.lower() for ch in allowed):
            return False

        try:
            await message.delete()
        except discord.Forbidden:
            return False

        await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Link: " + urls[0][:80])
        warn_count = await db.get_warn_count(message.guild.id, message.author.id)

        await message.channel.send(embed=link_blocked(message.author, urls[0], warn_count), delete_after=10)
        await self._dm(message.author, "🔗 LINK BLOQUEADO",
            "Tu mensaje fue eliminado en **" + message.guild.name + "** por contener un link.",
            COLOR_RED,
            [("📍 Canal", "#" + message.channel.name, True),
             ("🔗 Link", urls[0][:100], False),
             ("⚠️ Warns", str(warn_count) + "/5", True),
             ("📝 Tu mensaje", message.content[:500], False)])
        await self._log(message.guild, "link_blocked", message.author.id, details=urls[0][:100])
        return True

    async def _check_invite(self, message):
        content = message.content.lower()
        for pattern in INVITE_PATTERNS:
            if pattern in content:
                try:
                    await message.delete()
                except discord.Forbidden:
                    return False

                await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Invite link: " + pattern)
                warn_count = await db.get_warn_count(message.guild.id, message.author.id)

                await message.channel.send(embed=create_embed("🔗 INVITE BLOQUEADO",
                    message.author.mention + " intento enviar un link de invitacion",
                    COLOR_RED,
                    [("🔗 Patron", pattern, True),
                     ("⚠️ Warns", str(warn_count) + "/5", True)]), delete_after=10)
                await self._dm(message.author, "🔗 INVITE BLOQUEADO",
                    "Tu mensaje fue eliminado en **" + message.guild.name + "** por contener un link de invitacion.",
                    COLOR_RED,
                    [("📍 Canal", "#" + message.channel.name, True),
                     ("🔗 Patron", pattern, False),
                     ("⚠️ Warns", str(warn_count) + "/5", True),
                     ("📝 Tu mensaje", message.content[:500], False)])
                await self._log(message.guild, "invite_blocked", message.author.id, details="Patron: " + pattern)
                return True
        return False

    async def _check_phishing(self, message):
        content = message.content.lower()
        urls = re.findall(r'https?://[^\s]+', content)

        for url in urls:
            for domain in PHISHING_DOMAINS:
                if domain.lower() in url.lower():
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass

                    await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Phishing: " + url[:80])

                    try:
                        await message.author.ban(reason="Phishing: " + url[:80])
                    except discord.Forbidden:
                        pass

                    await message.channel.send(embed=phishing_detected(message.author, url), delete_after=10)
                    await self._dm(message.author, "🎣 PHISHING DETECTADO",
                        "Fuiste baneado de **" + message.guild.name + "** por enviar un link de phishing.",
                        COLOR_RED,
                        [("🔗 Link malicioso", url[:100], False),
                         ("📝 Tu mensaje", message.content[:500], False)])
                    await self._log(message.guild, "phishing_ban", message.author.id, details=url[:100])
                    return True
        return False

    async def _check_nsfw(self, message):
        content = message.content.lower()
        detected = False
        reason = ""

        for kw in NSFW_KEYWORDS:
            if kw in content:
                detected = True
                reason = "Texto NSFW: " + kw
                break

        if not detected:
            for att in message.attachments:
                if att.filename:
                    fn = att.filename.lower()
                    if any(x in fn for x in ["nsfw", "porn", "xxx", "nude", "hentai"]):
                        detected = True
                        reason = "Archivo NSFW: " + att.filename
                        break

        if not detected:
            return False

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        try:
            await message.author.ban(reason="NSFW: " + reason)
        except discord.Forbidden:
            try:
                until = discord.utils.utcnow() + timedelta(hours=24)
                await message.author.timeout(until, reason="NSFW: " + reason)
            except discord.Forbidden:
                pass

        await message.channel.send(embed=nsfw_detected(message.author), delete_after=10)
        await self._dm(message.author, "🚫 CONTENIDO NSFW",
            "Fuiste baneado de **" + message.guild.name + "** por contenido NSFW.",
            COLOR_RED,
            [("📝 Razon", reason, False)])
        await self._log(message.guild, "nsfw_ban", message.author.id, details=reason)
        return True

    async def _check_automod(self, message):
        content = message.content

        if len(content) > MIN_CAPS_LENGTH:
            caps = sum(1 for c in content if c.isupper())
            if (caps / len(content)) * 100 > MAX_CAPS_PERCENT:
                try:
                    await message.delete()
                    await self._alert_log(message.guild, "🔠 CAPS BLOQUEADOS",
                        message.author.mention + " - exceso de mayusculas en " + message.channel.mention,
                        COLOR_YELLOW)
                    return
                except discord.Forbidden:
                    pass

        lower = content.lower()
        for word in BANNED_WORDS:
            if word in lower:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass

                # BAN INMEDIATO por palabras extremas
                if word in BANNED_WORDS_BAN:
                    try:
                        await self._dm(message.author, "🔨 BAN INMEDIATO",
                            "Fuiste baneado de **" + message.guild.name + "** por contenido extremo.",
                            COLOR_RED,
                            [("📝 Razon", "Palabra extremamente prohibida: " + word, False),
                             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                        await message.author.ban(reason="Palabra prohibida extrema: " + word)
                    except discord.Forbidden:
                        pass
                    await self._alert_log(message.guild, "🔨 BAN INMEDIATO",
                        message.author.mention + " baneado por palabra extrema: `" + word + "`",
                        COLOR_RED)
                    await self._log(message.guild, "banned_word_ban", message.author.id, details="EXTREMO: " + word)
                    return

                # Warn normal
                await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Palabra prohibida: " + word)
                warn_count = await db.get_warn_count(message.guild.id, message.author.id)

                # BAN por reincidencia (3 palabras prohibidas)
                if warn_count >= BAD_WORD_BAN_THRESHOLD:
                    try:
                        await self._dm(message.author, "🔨 BAN POR PALABRAS PROHIBIDAS",
                            "Fuiste baneado de **" + message.guild.name + "** por reincidencia en palabras prohibidas.",
                            COLOR_RED,
                            [("🔢 Total palabras prohibidas", str(warn_count), True),
                             ("📋 Razon", "Mas de " + str(BAD_WORD_BAN_THRESHOLD) + " palabras prohibidas", False),
                             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                        await message.author.ban(reason="Reincidencia: " + str(warn_count) + " palabras prohibidas")
                    except discord.Forbidden:
                        pass
                    await self._alert_log(message.guild, "🔨 BAN POR REINCIDENCIA",
                        message.author.mention + " baneado por " + str(warn_count) + " palabras prohibidas",
                        COLOR_RED)
                    await self._log(message.guild, "banned_word_ban", message.author.id,
                                    details="Reincidencia: " + str(warn_count) + " palabras")
                    return

                await self._dm(message.author, "🚫 PALABRA PROHIBIDA",
                    "Tu mensaje fue eliminado en **" + message.guild.name + "**.",
                    COLOR_RED,
                    [("📍 Canal", "#" + message.channel.name, True),
                     ("⚠️ Palabras prohibidas", str(warn_count) + "/" + str(BAD_WORD_BAN_THRESHOLD) + " (ban)", True),
                     ("Tu mensaje", content[:500], False),
                     ("⚠️ Siguiente", "Ban automatico si alcanzas " + str(BAD_WORD_BAN_THRESHOLD), False)])
                await self._log(message.guild, "banned_word", message.author.id, details="Palabra: " + word)
                return

        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+", flags=re.UNICODE)
        if len(emoji_pattern.findall(content)) > MAX_EMOJI_COUNT:
            try:
                await message.delete()
                await self._alert_log(message.guild, "😀 EMOJIS BLOQUEADOS",
                    message.author.mention + " - exceso de emojis", COLOR_YELLOW)
            except discord.Forbidden:
                pass

    async def _handle_bot(self, member):
        guild = member.guild
        inviter = None
        try:
            async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    inviter = entry.user
                    break
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason="Bot no autorizado")
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "🤖 BOT NO AUTORIZADO",
            str(member) + " fue baneado (bot no autorizado)" +
            ("\n" + str(inviter) + " fue expulsado por invitarlo" if inviter else ""),
            COLOR_RED)

        if inviter and not inviter.bot:
            try:
                await self._dm(inviter, "👢 EXPULSADO",
                    "Fuiste expulsado de **" + guild.name + "** por invitar un bot no autorizado.",
                    COLOR_RED,
                    [("🤖 Bot baneado", str(member), True)])
                await inviter.kick(reason="Invitó bot no autorizado")
            except (discord.Forbidden, Exception):
                pass

        await self._log(guild, "unauthorized_bot", member.id,
                        inviter.id if inviter else None,
                        details="Bot: " + member.name)

    # ==========================================
    #  COMANDOS
    # ==========================================

    @app_commands.command(name="security", description="Ver estado de seguridad del servidor")
    async def security_cmd(self, interaction: discord.Interaction):
        settings = await db.get_settings(interaction.guild.id)
        if not settings:
            await db.ensure_settings(interaction.guild.id)
            settings = await db.get_settings(interaction.guild.id)
        await interaction.response.send_message(
            embed=security_status(interaction.guild, settings))

    @app_commands.command(name="raid", description="Configurar anti-raid")
    @app_commands.describe(threshold="Joins para activar", window="Segundos de ventana")
    async def raid_cmd(self, interaction: discord.Interaction, threshold: int = None, window: int = None):
        if not self._has_role(interaction):
            return
        updates = {}
        if threshold:
            updates["raid_threshold"] = threshold
        if window:
            updates["raid_window"] = window
        if updates:
            await db.update_settings(interaction.guild.id, **updates)
        settings = await db.get_settings(interaction.guild.id) or {}
        th = settings.get("raid_threshold", RAID_JOIN_THRESHOLD)
        wn = settings.get("raid_window", RAID_TIME_WINDOW)
        await interaction.response.send_message(embed=create_embed("🚨 Anti-Raid Config",
            "Configurado correctamente", COLOR_GREEN,
            [("👥 Umbral", str(th) + " joins", True),
             ("⏱️ Ventana", str(wn) + "s", True)]))

    @app_commands.command(name="antispam", description="Configurar anti-spam")
    @app_commands.describe(threshold="Mensajes para activar", mute_duration="Duracion del mute en segundos")
    async def antispam_cmd(self, interaction: discord.Interaction, threshold: int = None, mute_duration: int = None):
        if not self._has_role(interaction):
            return
        updates = {}
        if threshold:
            updates["spam_threshold"] = threshold
        if mute_duration:
            updates["mute_duration"] = mute_duration
        if updates:
            await db.update_settings(interaction.guild.id, **updates)
        settings = await db.get_settings(interaction.guild.id) or {}
        th = settings.get("spam_threshold", SPAM_THRESHOLD)
        md = settings.get("mute_duration", MUTE_DEFAULT_DURATION)
        await interaction.response.send_message(embed=create_embed("🚫 Anti-Spam Config",
            "Configurado correctamente", COLOR_GREEN,
            [("💬 Umbral", str(th) + " msgs", True),
             ("🔇 Mute", str(md) + "s", True)]))

    # ==========================================
    #  UTILIDADES
    # ==========================================

    def _has_role(self, interaction):
        if any(r.name in SECURITY_ROLES for r in interaction.user.roles):
            return True
        import asyncio
        asyncio.get_event_loop().create_task(
            interaction.response.send_message(
                embed=create_embed("❌ Sin permisos", "Necesitas un rol de moderador.", COLOR_RED),
                ephemeral=True))
        return False

    async def _dm(self, user, title, description, color, fields=None):
        try:
            await user.send(embed=create_embed(title, description, color, fields))
        except discord.Forbidden:
            pass

    async def _alert_log(self, guild, title, description, color):
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(embed=create_embed(title, description, color))
                except discord.Forbidden:
                    pass

    async def _log(self, guild, event_type, user_id=None, moderator_id=None, details=None):
        await db.add_log(guild.id, event_type, user_id, moderator_id, details)


async def setup(bot):
    await bot.add_cog(Security(bot))
