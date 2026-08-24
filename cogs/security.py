"""
cogs/security.py - Motor de Seguridad v7
Anti-Raid, Anti-Spam, Anti-Flood, Anti-Links, Anti-Phishing
Anti-NSFW, Anti-Bots, Anti-Extension, Auto-Mod, Deteccion de Alts
Anti-Aplicacion, Acciones Anormales, Logs Completos
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
    ANTI_APP_ENABLED, ALLOWED_APPS,
    ABNORMAL_ACTION_THRESHOLD, ABNORMAL_ACTION_WINDOW,
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
        # Track abnormal actions per user per guild
        self._abnormal_actions = defaultdict(lambda: defaultdict(list))
        # Track channel creates for nuke detection
        self._channel_create_times = defaultdict(list)
        # Track integrations
        self._known_integrations = {}

    # ==========================================
    #  EVENTOS - MIEMBROS
    # ==========================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = await db.get_settings(guild.id) or {}
        await db.ensure_settings(guild.id)

        # Log completo
        account_age = (datetime.utcnow() - member.created_at).days
        await self._log(guild, "member_join", member.id,
                        details="Cuenta: " + str(account_age) + " dias | Bot: " + str(member.bot))

        # Embed de log al canal
        await self._alert_log(guild, "📥 MIEMBRO UNIDO",
            member.mention + " se unio al servidor",
            COLOR_GREEN,
            [
                ("👤 Usuario", str(member) + "\n`" + str(member.id) + "`", True),
                ("📅 Cuenta creada", "<t:" + str(int(member.created_at.timestamp())) + ":R>\n(" + str(account_age) + " dias)", True),
                ("👥 Total miembros", str(guild.member_count), True),
            ])

        if member.bot:
            await self._handle_bot(member)
            return

        if settings.get("anti_raid", True):
            await self._check_raid(member)

        if account_age < ALT_ACCOUNT_DAYS:
            await self._alert_log(guild, "🔍 CUENTA NUEVA SOSPECHOSA",
                member.mention + " tiene una cuenta de solo **" + str(account_age) + " dias** (posible alt)",
                COLOR_ORANGE,
                [
                    ("👤 Usuario", member.mention + "\n`" + str(member.id) + "`", True),
                    ("📅 Edad de cuenta", str(account_age) + " dias", True),
                    ("⚠️ Umbral", str(ALT_ACCOUNT_DAYS) + " dias", True),
                ])

        if await db.is_blacklisted(guild.id, member.id):
            try:
                await member.ban(reason="Auto-ban: en blacklist")
                await self._log(guild, "blacklist_ban", member.id, details="En blacklist")
                await self._alert_log(guild, "🔨 BLACKLIST BAN",
                    member.mention + " fue baneado automaticamente (en blacklist)",
                    COLOR_RED,
                    [("👤 Usuario", member.mention, True), ("📋 Razon", "En blacklist", False)])
            except discord.Forbidden:
                pass

        if member.name.lower() in SUSPICIOUS_NAMES or member.display_name.lower() in SUSPICIOUS_NAMES:
            await self._alert_log(guild, "🔍 NOMBRE SOSPECHOSO",
                member.mention + " tiene un nombre sospechoso: `" + member.name + "`",
                COLOR_ORANGE,
                [("👤 Usuario", member.mention, True), ("📝 Nombre", member.name, True)])

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.guild:
            return
        guild = member.guild

        # Buscar razon del kick/ban en audit log
        reason = "Desconocido"
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5):
                if entry.target.id == member.id:
                    reason = entry.reason or "Sin razon"
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        # Log completo al canal
        mod_text = str(moderator) if moderator else "Desconocido"
        await self._alert_log(guild, "📤 MIEMBRO SALIO",
            member.mention + " salio del servidor",
            COLOR_YELLOW,
            [
                ("👤 Usuario", str(member) + "\n`" + str(member.id) + "`", True),
                ("📝 Razon", reason, True),
                ("👮 Moderador", mod_text, True),
                ("👥 Miembros restantes", str(guild.member_count - 1), True),
            ])
        await self._log(guild, "member_leave", member.id, details="Razon: " + reason)

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
                            kick_count = len(self._kick_times[guild.id])
                            try:
                                dm = create_embed("🔨 BAN - MASS KICK",
                                    "Fuiste baneado de **" + guild.name + "** por expulsar multiples usuarios",
                                    COLOR_RED,
                                    [("📝 Razon", "Expulsion masiva", False),
                                     ("🔢 Usuarios expulsados", str(kick_count), True),
                                     ("⏱️ Ventana", str(MASS_KICK_TIME_WINDOW) + "s", True),
                                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                                await user.send(embed=dm)
                            except discord.Forbidden:
                                pass
                            try:
                                await user.ban(reason="Mass kick: " + str(kick_count) + " kicks en " + str(MASS_KICK_TIME_WINDOW) + "s")
                            except discord.Forbidden:
                                pass
                            await self._alert_log(guild, "🔨 BAN - MASS KICK DETECTADO",
                                user.mention + " fue **BANEADO** por expulsar **" + str(kick_count) + "** usuarios en " + str(MASS_KICK_TIME_WINDOW) + "s",
                                COLOR_RED,
                                [("👤 Responsable", user.mention + "\n`" + str(user.id) + "`", True),
                                 ("🔢 Kicks", str(kick_count), True),
                                 ("⏱️ Ventana", str(MASS_KICK_TIME_WINDOW) + "s", True),
                                 ("⚡ Accion", "BAN automatico", True)])
                            await self._log(guild, "mass_kick_ban", user.id,
                                            details=str(kick_count) + " kicks en " + str(MASS_KICK_TIME_WINDOW) + "s")
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
                            ban_count = len(self._ban_times[guild.id])
                            try:
                                dm = create_embed("🔨 BAN - MASS BAN",
                                    "Fuiste baneado de **" + guild.name + "** por banear multiples usuarios",
                                    COLOR_RED,
                                    [("📝 Razon", "Baneo masivo", False),
                                     ("🔢 Usuarios baneados", str(ban_count), True),
                                     ("⏱️ Ventana", str(MASS_BAN_TIME_WINDOW) + "s", True),
                                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                                await user.send(embed=dm)
                            except discord.Forbidden:
                                pass
                            try:
                                await user.ban(reason="Mass ban: " + str(ban_count) + " bans en " + str(MASS_BAN_TIME_WINDOW) + "s")
                            except discord.Forbidden:
                                pass
                            await self._alert_log(guild, "🔨 BAN - MASS BAN DETECTADO",
                                user.mention + " fue **BANEADO** por banear **" + str(ban_count) + "** usuarios en " + str(MASS_BAN_TIME_WINDOW) + "s",
                                COLOR_RED,
                                [("👤 Responsable", user.mention + "\n`" + str(user.id) + "`", True),
                                 ("🔢 Bans", str(ban_count), True),
                                 ("⏱️ Ventana", str(MASS_BAN_TIME_WINDOW) + "s", True),
                                 ("⚡ Accion", "BAN automatico", True)])
                            await self._log(guild, "mass_ban_ban", user.id,
                                            details=str(ban_count) + " bans en " + str(MASS_BAN_TIME_WINDOW) + "s")
                            break
                except discord.Forbidden:
                    pass
                self._ban_times[guild.id] = []

    # ==========================================
    #  EVENTOS - MENSAJES
    # ==========================================

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
        content_preview = message.content[:200] if message.content else "(sin texto)"
        await self._alert_log(message.guild, "🗑️ MENSAJE ELIMINADO",
            message.author.mention + " - mensaje eliminado en " + message.channel.mention,
            COLOR_YELLOW,
            [
                ("👤 Autor", message.author.mention + "\n`" + str(message.author.id) + "`", True),
                ("📍 Canal", message.channel.mention, True),
                ("📝 Contenido", content_preview, False),
                ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
            ])
        await self._log(message.guild, "message_delete", message.author.id,
                        details="Canal: " + message.channel.mention + " | Msg: " + content_preview)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        await self._alert_log(before.guild, "✏️ MENSAJE EDITADO",
            before.author.mention + " edito un mensaje en " + before.channel.mention,
            COLOR_BLUE,
            [
                ("👤 Autor", before.author.mention, True),
                ("📍 Canal", before.channel.mention, True),
                ("📝 Antes", before.content[:500] if before.content else "(vacio)", False),
                ("📝 Despues", after.content[:500] if after.content else "(vacio)", False),
            ])
        await self._log(before.guild, "message_edit", before.author.id,
                        details="Canal: " + before.channel.name)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        action = ""
        if before.channel is None and after.channel:
            action = "Conectado a " + after.channel.name
        elif before.channel and after.channel is None:
            action = "Desconectado de " + before.channel.name
        elif before.channel != after.channel:
            action = "Movido de " + before.channel.name + " a " + after.channel.name
        elif before.self_mute != after.self_mute:
            action = "Self-mute cambiado"
        elif before.self_deaf != after.self_deaf:
            action = "Self-deaf cambiado"
        if action:
            await self._alert_log(member.guild, "🔊 VOICE UPDATE",
                member.mention + " — " + action,
                COLOR_BLUE,
                [("👤 Usuario", member.mention, True),
                 ("📍 Accion", action, True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            await self._log(member.guild, "voice_state", member.id, details=action)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot:
            return
        changes = []
        if before.nick != after.nick:
            changes.append("Nickname: " + str(before.nick) + " -> " + str(after.nick))
        if before.roles != after.roles:
            added_roles = [r.name for r in after.roles if r not in before.roles]
            removed_roles = [r.name for r in before.roles if r not in after.roles]
            if added_roles:
                changes.append("Roles agregados: " + ", ".join(added_roles))
            if removed_roles:
                changes.append("Removidos: " + ", ".join(removed_roles))
        if before.avatar != after.avatar:
            changes.append("Avatar cambiado")
        if changes:
            changes_str = "\n".join(changes)
            await self._alert_log(after.guild, "👤 MIEMBRO MODIFICADO",
                after.mention + " fue modificado",
                COLOR_BLUE,
                [("👤 Usuario", after.mention + "\n`" + str(after.id) + "`", True),
                 ("📝 Cambios", changes_str, False),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            await self._log(after.guild, "member_update", after.id, details=changes_str)

    # ==========================================
    #  EVENTOS - CANALES
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        now = time.time()
        creator = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    creator = entry.user.mention if not entry.user.bot else "Bot: " + entry.user.name
                    # Track for nuke detection
                    self._channel_create_times[guild.id].append(now)
                    self._channel_create_times[guild.id] = [
                        t for t in self._channel_create_times[guild.id]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    # Track abnormal actions
                    if not entry.user.bot:
                        uid = entry.user.id
                        self._abnormal_actions[guild.id][uid].append(("channel_create", now))
                        self._abnormal_actions[guild.id][uid] = [
                            (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                            if now - t < ABNORMAL_ACTION_WINDOW
                        ]
                        if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                            await self._punish_abnormal(entry.user, guild, "crear canales rapidamente")
                    break
        except discord.Forbidden:
            pass

        # Si se crean muchos canales = nuke
        from config import NUKE_CHANNEL_CREATE
        if len(self._channel_create_times[guild.id]) >= NUKE_CHANNEL_CREATE:
            await self._alert_log(guild, "🚨 NUKE DETECTADO - CANALES CREADOS",
                str(len(self._channel_create_times[guild.id])) + " canales creados en " + str(ABNORMAL_ACTION_WINDOW) + "s",
                COLOR_RED,
                [("🔢 Canales", str(len(self._channel_create_times[guild.id])), True),
                 ("⏱️ Ventana", str(ABNORMAL_ACTION_WINDOW) + "s", True),
                 ("⚡ Accion", "Auto-lockdown + investigacion", True)])
            self._channel_create_times[guild.id] = []

        await self._alert_log(guild, "📁 CANAL CREADO",
            "Nuevo canal: **#" + channel.name + "**\nCreado por: " + str(creator),
            COLOR_GREEN,
            [("📍 Canal", channel.mention, True),
             ("📋 Tipo", str(channel.type), True),
             ("👷 Creado por", str(creator), True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "channel_create", details="Canal: #" + channel.name + " | Creado por: " + str(creator))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        user_text = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id and not entry.user.bot:
                    user = entry.user
                    user_text = user.mention

                    # Track abnormal actions
                    uid = user.id
                    now = time.time()
                    self._abnormal_actions[guild.id][uid].append(("channel_delete", now))
                    self._abnormal_actions[guild.id][uid] = [
                        (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                        await self._punish_abnormal(user, guild, "eliminar canales rapidamente")

                    # BAN INMEDIATO al admin que borra un canal
                    try:
                        dm = create_embed("🔨 BAN - CANAL ELIMINADO",
                            "Fuiste baneado de **" + guild.name + "** por eliminar el canal **" + channel.name + "**",
                            COLOR_RED,
                            [("📍 Canal eliminado", channel.name, True),
                             ("📋 ID del canal", str(channel.id), True),
                             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
                             ("📋 Razon", "Eliminar canales no esta permitido", False)])
                        await user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    try:
                        await user.ban(reason="Elimino el canal: " + channel.name)
                    except discord.Forbidden:
                        pass
                    break
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "🗑️ CANAL ELIMINADO",
            "Canal **#" + channel.name + "** fue eliminado\nResponsable: " + user_text,
            COLOR_RED,
            [("📍 Canal", "#" + channel.name, True),
             ("📋 ID", str(channel.id), True),
             ("👷 Eliminado por", user_text, True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "channel_delete", details="Canal: #" + channel.name + " | Por: " + user_text)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append("Nombre: " + before.name + " -> " + after.name)
        if before.topic != after.topic:
            changes.append("Tema modificado")
        if before.nsfw != after.nsfw:
            changes.append("NSFW: " + str(before.nsfw) + " -> " + str(after.nsfw))
        if before.slowmode_delay != after.slowmode_delay:
            changes.append("Slowmode: " + str(before.slowmode_delay) + "s -> " + str(after.slowmode_delay) + "s")
        if before.category != after.category:
            cat_before = before.category.name if before.category else "Ninguna"
            cat_after = after.category.name if after.category else "Ninguna"
            changes.append("Categoria: " + cat_before + " -> " + cat_after)
        if not changes:
            return

        guild = before.guild
        user_text = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id and not entry.user.bot:
                    user_text = entry.user.mention
                    user = entry.user
                    changes_str = "\n".join(changes)

                    # Track abnormal actions
                    now = time.time()
                    uid = user.id
                    self._abnormal_actions[guild.id][uid].append(("channel_update", now))
                    self._abnormal_actions[guild.id][uid] = [
                        (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                        await self._punish_abnormal(user, guild, "modificar canales rapidamente")

                    name_change = any("nombre" in c.lower() for c in changes)

                    if name_change:
                        try:
                            dm = create_embed("✏️ CANAL EDITADO",
                                "Editaste **" + after.name + "** en **" + guild.name + "**",
                                COLOR_YELLOW,
                                [("📍 Canal", after.mention, True),
                                 ("📝 Cambios", changes_str, False),
                                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                    break
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "✏️ CANAL EDITADO",
            "**#" + after.name + "** fue modificado por " + user_text,
            COLOR_YELLOW,
            [("📍 Canal", after.mention, True),
             ("📝 Cambios", "\n".join(changes), False),
             ("👷 Editado por", user_text, True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "channel_update", details="Canal: #" + after.name + " | Cambios: " + "\n".join(changes))

    # ==========================================
    #  EVENTOS - ROLES
    # ==========================================

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

        creator = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id and not entry.user.bot:
                    creator = entry.user.mention
                    user = entry.user
                    role_name = role.name

                    # Track abnormal actions
                    now = time.time()
                    uid = user.id
                    self._abnormal_actions[guild.id][uid].append(("role_create", now))
                    self._abnormal_actions[guild.id][uid] = [
                        (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                        await self._punish_abnormal(user, guild, "crear roles rapidamente")

                    if found:
                        perm_str = ", ".join(found)
                        try:
                            await role.delete(reason="Rol con permisos peligrosos bloqueados")
                        except discord.Forbidden:
                            pass
                        try:
                            dm = create_embed("🎭 ROL PELIGROSO ELIMINADO",
                                "Creaste el rol **" + role_name + "** con permisos peligrosos en **" + guild.name + "**",
                                COLOR_RED,
                                [("⚠️ Permisos peligrosos", perm_str, False),
                                 ("📍 Guild", guild.name, True),
                                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                    break
        except discord.Forbidden:
            pass

        perm_detail = ", ".join(found) if found else "Ninguno"
        danger_text = " **PELIGROSO**" if found else ""
        await self._alert_log(guild, "🎭 ROL CREADO" + danger_text,
            "Nuevo rol: **" + role.name + "**\nCreado por: " + str(creator),
            COLOR_RED if found else COLOR_GREEN,
            [("🎭 Rol", role.mention, True),
             ("👷 Creado por", str(creator), True),
             ("🔑 Permisos peligrosos", perm_detail, True),
             ("🎨 Color", str(role.color), True),
             ("📋 ID", "`" + str(role.id) + "`", True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "role_create", details="Rol: " + role.name + " | Peligrosos: " + perm_detail)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not ANTI_ROLE_DELETE_ENABLED:
            return
        guild = role.guild
        now = time.time()

        # Log who deleted it
        deleter = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id and not entry.user.bot:
                    deleter = entry.user.mention
                    user = entry.user

                    # Track abnormal actions
                    uid = user.id
                    self._abnormal_actions[guild.id][uid].append(("role_delete", now))
                    self._abnormal_actions[guild.id][uid] = [
                        (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                        await self._punish_abnormal(user, guild, "eliminar roles rapidamente")
                    break
        except discord.Forbidden:
            pass

        # Track role deletes for nuke detection
        if not hasattr(self, '_role_delete_times'):
            self._role_delete_times = defaultdict(list)
        self._role_delete_times[guild.id].append(now)
        self._role_delete_times[guild.id] = [
            t for t in self._role_delete_times[guild.id]
            if now - t < ROLE_DELETE_TIME_WINDOW
        ]
        if len(self._role_delete_times[guild.id]) >= ROLE_DELETE_THRESHOLD:
            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.role_delete):
                    if not entry.user.bot:
                        user = entry.user
                        count = len(self._role_delete_times[guild.id])
                        try:
                            dm = create_embed("🔨 BAN - MASS ROLE DELETE",
                                "Fuiste baneado de **" + guild.name + "** por eliminar multiples roles",
                                COLOR_RED,
                                [("📝 Razon", "Eliminacion masiva de roles", False),
                                 ("🔢 Roles eliminados", str(count), True),
                                 ("⏱️ Ventana", str(ROLE_DELETE_TIME_WINDOW) + "s", True),
                                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                            await user.send(embed=dm)
                        except discord.Forbidden:
                            pass
                        try:
                            await user.ban(reason="Mass role delete: " + str(count) + " roles")
                        except discord.Forbidden:
                            pass
                        await self._alert_log(guild, "🔨 BAN - MASS ROLE DELETE",
                            user.mention + " fue **BANEADO** por eliminar **" + str(count) + "** roles en " + str(ROLE_DELETE_TIME_WINDOW) + "s",
                            COLOR_RED,
                            [("👤 Responsable", user.mention + "\n`" + str(user.id) + "`", True),
                             ("🔢 Roles eliminados", str(count), True),
                             ("⏱️ Ventana", str(ROLE_DELETE_TIME_WINDOW) + "s", True),
                             ("⚡ Accion", "BAN automatico", True)])
                        await self._log(guild, "mass_role_delete_ban", user.id,
                                        details=str(count) + " roles eliminados")
                        break
            except discord.Forbidden:
                pass
            self._role_delete_times[guild.id] = []

        await self._alert_log(guild, "🎭 ROL ELIMINADO",
            "Rol **" + role.name + "** fue eliminado\nResponsable: " + str(deleter),
            COLOR_RED,
            [("🎭 Rol", role.name, True),
             ("👷 Eliminado por", str(deleter), True),
             ("📋 ID", "`" + str(role.id) + "`", True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "role_delete", details="Rol: " + role.name + " | Por: " + str(deleter))

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append("Nombre: " + before.name + " -> " + after.name)
        if before.color != after.color:
            changes.append("Color cambiado")
        if before.permissions != after.permissions:
            new_perms = [p for p, v in after.permissions if v and not before.permissions[p]]
            lost_perms = [p for p, v in before.permissions if v and not after.permissions[p]]
            if new_perms:
                changes.append("Permisos agregados: " + ", ".join(new_perms))
            if lost_perms:
                changes.append("Permisos removidos: " + ", ".join(lost_perms))
        if not changes:
            return

        changes_str = "\n".join(changes)
        updater = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_update):
                if entry.target.id == after.id and not entry.user.bot:
                    updater = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        await self._alert_log(after.guild, "🎭 ROL MODIFICADO",
            "Rol **" + after.name + "** fue modificado por " + str(updater),
            COLOR_YELLOW,
            [("🎭 Rol", after.mention, True),
             ("📝 Cambios", changes_str, False),
             ("👷 Modificado por", str(updater), True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(after.guild, "role_update", details="Rol: " + after.name + " | " + changes_str)

    # ==========================================
    #  EVENTOS - EMOJIS
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        if added:
            creator = "Desconocido"
            try:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.emoji_create):
                    if not entry.user.bot:
                        creator = entry.user.mention
                        break
            except discord.Forbidden:
                pass

            emoji_names = ", ".join([e.name for e in added[:10]])
            if len(added) >= 5:
                await self._alert_log(guild, "😀 SPAM DE EMOJIS",
                    str(len(added)) + " emojis agregados de una vez por " + str(creator),
                    COLOR_RED,
                    [("😀 Emojis", emoji_names, False),
                     ("🔢 Total", str(len(added)), True),
                     ("👷 Agregados por", str(creator), True)])
            else:
                await self._alert_log(guild, "😀 EMOJIS AGREGADOS",
                    str(len(added)) + " emojis nuevos: " + emoji_names,
                    COLOR_YELLOW,
                    [("😀 Emojis", emoji_names, False),
                     ("🔢 Total", str(len(added)), True),
                     ("👷 Agregados por", str(creator), True)])
            await self._log(guild, "emoji_add", details=str(len(added)) + " emojis: " + emoji_names)

        if removed:
            emoji_names = ", ".join([e.name for e in removed[:10]])
            await self._alert_log(guild, "😀 EMOJIS ELIMINADOS",
                str(len(removed)) + " emojis eliminados",
                COLOR_YELLOW,
                [("😀 Emojis", emoji_names, False),
                 ("🔢 Total", str(len(removed)), True)])
            await self._log(guild, "emoji_remove", details=str(len(removed)) + " emojis: " + emoji_names)

    # ==========================================
    #  EVENTOS - WEBHOOKS
    # ==========================================

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                if not entry.user.bot:
                    ch_name = channel.name
                    try:
                        dm = create_embed("🔗 WEBHOOK CREADO",
                            "Creaste un webhook en **" + ch_name + "** en **" + guild.name + "**",
                            COLOR_YELLOW,
                            [("📍 Canal", channel.mention, True),
                             ("⚠️ Nota", "Los webhooks son monitoreados por seguridad", False),
                             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                        await entry.user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    break
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "🔗 WEBHOOK ACTUALIZADO",
            "Webhooks actualizados en " + channel.mention,
            COLOR_ORANGE,
            [("📍 Canal", channel.mention, True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "webhook_update", details="Canal: " + channel.name)

    # ==========================================
    #  EVENTOS - INTEGRACIONES / APLICACIONES
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        if not ANTI_APP_ENABLED:
            return
        try:
            integrations = await guild.integrations()
            for integration in integrations:
                app_name = integration.name
                app_id = str(integration.id) if hasattr(integration, 'id') else "N/A"
                app_type = type(integration).__name__

                # Check if it's in the allowed list
                if ALLOWED_APPS and app_name in ALLOWED_APPS:
                    continue

                # Log the integration
                await self._alert_log(guild, "🔌 APLICACION DETECTADA",
                    "Nueva aplicacion/integracion detectada: **" + app_name + "**",
                    COLOR_ORANGE,
                    [("📦 Aplicacion", app_name, True),
                     ("📋 ID", "`" + app_id + "`", True),
                     ("📋 Tipo", app_type, True),
                     ("📍 Servidor", guild.name, True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
                     ("⚠️ Nota", "Monitoreada por seguridad", False)])
                await self._log(guild, "app_detected", details="App: " + app_name + " | Tipo: " + app_type)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append("Nombre: " + before.name + " -> " + after.name)
        if before.icon != after.icon:
            changes.append("Icono cambiado")
        if before.splash != after.splash:
            changes.append("Splash cambiado")
        if before.premium_tier != after.premium_tier:
            changes.append("Boost: Nivel " + str(before.premium_tier) + " -> " + str(after.premium_tier))
        if before.verification_level != after.verification_level:
            changes.append("Verificacion: " + str(before.verification_level) + " -> " + str(after.verification_level))
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append("Filtro de contenido cambiado")
        if before.default_notifications != after.default_notifications:
            changes.append("Notificaciones por defecto cambiadas")

        if not changes:
            return

        changes_str = "\n".join(changes)
        await self._alert_log(after.guild, "⚙️ SERVIDOR MODIFICADO",
            "Configuracion del servidor fue modificada",
            COLOR_ORANGE,
            [("📝 Cambios", changes_str, False),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(after.guild, "guild_update", details=changes_str)

    # ==========================================
    #  MONITOREO DE BANS
    # ==========================================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        moderator = "Desconocido"
        reason = "Sin razon"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id and not entry.user.bot:
                    moderator = entry.user.mention
                    reason = entry.reason or "Sin razon"

                    # Track abnormal actions
                    uid = entry.user.id
                    now = time.time()
                    self._abnormal_actions[guild.id][uid].append(("ban", now))
                    self._abnormal_actions[guild.id][uid] = [
                        (a, t) for a, t in self._abnormal_actions[guild.id][uid]
                        if now - t < ABNORMAL_ACTION_WINDOW
                    ]
                    if len(self._abnormal_actions[guild.id][uid]) >= ABNORMAL_ACTION_THRESHOLD:
                        await self._punish_abnormal(entry.user, guild, "banear usuarios rapidamente")
                    break
        except discord.Forbidden:
            pass

        try:
            dm = create_embed("🔨 HAS SIDO BANEADO",
                "Fuiste baneado de **" + guild.name + "**",
                COLOR_RED,
                [("📝 Razon", reason, False),
                 ("👮 Moderador", str(moderator), True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
                 ("📋 ID del usuario", "`" + str(user.id) + "`", True)])
            await user.send(embed=dm)
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "🔨 BAN EJECUTADO",
            str(moderator) + " baneo a **" + str(user) + "**",
            COLOR_RED,
            [("👤 Usuario baneado", str(user) + "\n`" + str(user.id) + "`", True),
             ("📝 Razon", reason, False),
             ("👮 Moderador", str(moderator), True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "member_ban", user.id, details="Razon: " + reason + " | Por: " + str(moderator))

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        moderator = "Desconocido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        try:
            dm = create_embed("✅ DESBANEADO",
                "Has sido desbaneado de **" + guild.name + "**",
                COLOR_GREEN,
                [("👮 Moderador", str(moderator), True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            await user.send(embed=dm)
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "✅ DESBAN EJECUTADO",
            str(moderator) + " desbaneo a **" + str(user) + "**",
            COLOR_GREEN,
            [("👤 Usuario", str(user) + "\n`" + str(user.id) + "`", True),
             ("👮 Moderador", str(moderator), True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "member_unban", user.id, details="Desbaneado por: " + str(moderator))

    # ==========================================
    #  MOTOR DE SEGURIDAD - ACCIONES ANORMALES
    # ==========================================

    async def _punish_abnormal(self, user, guild, action_desc):
        """Expulsa a un usuario por acciones anormales"""
        count = len(self._abnormal_actions[guild.id][user.id])
        try:
            dm = create_embed("👢 EXPULSADO - ACCIONES ANORMALES",
                "Fuiste expulsado de **" + guild.name + "** por " + action_desc,
                COLOR_RED,
                [("📝 Razon", str(count) + " acciones en " + str(ABNORMAL_ACTION_WINDOW) + "s: " + action_desc, False),
                 ("⏱️ Ventana", str(ABNORMAL_ACTION_WINDOW) + " segundos", True),
                 ("🔢 Acciones", str(count) + "/" + str(ABNORMAL_ACTION_THRESHOLD), True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            await user.send(embed=dm)
        except discord.Forbidden:
            pass
        try:
            await user.kick(reason="Acciones anormales: " + action_desc + " (" + str(count) + " en " + str(ABNORMAL_ACTION_WINDOW) + "s)")
        except discord.Forbidden:
            pass

        await self._alert_log(guild, "👢 KICK - ACCIONES ANORMALES",
            user.mention + " fue expulsado por " + action_desc,
            COLOR_RED,
            [("👤 Usuario", user.mention + "\n`" + str(user.id) + "`", True),
             ("📝 Razon", str(count) + " acciones en " + str(ABNORMAL_ACTION_WINDOW) + "s", False),
             ("⏱️ Ventana", str(ABNORMAL_ACTION_WINDOW) + "s", True),
             ("⚡ Accion", "KICK automatico", True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._log(guild, "abnormal_action_kick", user.id,
                        details=str(count) + " acciones: " + action_desc)
        self._abnormal_actions[guild.id][user.id] = []

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
                str(len(self.join_times[gid])) + " usuarios se unieron en " + str(window) + " segundos",
                COLOR_RED,
                [("👥 Usuarios", str(len(self.join_times[gid])), True),
                 ("⏱️ Ventana", str(window) + "s", True),
                 ("⚡ Accion", "Auto-ban de todos los involucrados", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

            recent = [
                m for m in member.guild.members
                if m.joined_at and (datetime.utcnow() - m.joined_at).total_seconds() < window
                and not m.bot
            ]
            for m in recent:
                try:
                    dm = create_embed("🚨 BAN POR RAID",
                        "Fuiste baneado de **" + member.guild.name + "** por ser parte de un raid.",
                        COLOR_RED,
                        [("📝 Razon", "Raid: " + str(len(self.join_times[gid])) + " joins en " + str(window) + "s", False),
                         ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
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
                     ("⏱️ Duracion", str(duration // 60) + " minutos", True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                await self._alert_log(message.guild, "🔇 SPAM MUTE",
                    message.author.mention + " fue silenciado por spam",
                    COLOR_BLUE,
                    [("👤 Usuario", message.author.mention, True),
                     ("🔢 Mensajes", str(count) + " en " + str(SPAM_TIME_WINDOW) + "s", True),
                     ("⏱️ Duracion", str(duration // 60) + " min", True),
                     ("📍 Canal", message.channel.mention, True)])
                await self._log(message.guild, "spam_mute", uid, details=str(count) + " msgs en " + str(SPAM_TIME_WINDOW) + "s")
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
                     ("🔇 Duracion", str(MUTE_DEFAULT_DURATION // 60) + " min", True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                await self._alert_log(message.guild, "⚡ FLOOD MUTE",
                    message.author.mention + " fue silenciado por flood",
                    COLOR_ORANGE,
                    [("👤 Usuario", message.author.mention, True),
                     ("🔢 Mensajes rapidos", str(count) + " en " + str(FLOOD_TIME_WINDOW) + "s", True),
                     ("⚠️ Warns", str(warn_count), True),
                     ("📍 Canal", message.channel.mention, True)])
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
             ("📝 Tu mensaje", message.content[:500], False),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._alert_log(message.guild, "📢 MENCIONES BLOQUEADAS",
            message.author.mention + " menciono a " + str(count) + " personas en " + message.channel.mention,
            COLOR_RED,
            [("👤 Usuario", message.author.mention, True),
             ("📢 Menciones", str(count), True),
             ("⚠️ Warns", str(warn_count), True),
             ("📝 Mensaje", message.content[:300], False)])
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
             ("📝 Tu mensaje", message.content[:500], False),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._alert_log(message.guild, "🔗 LINK ELIMINADO",
            message.author.mention + " envio un link en " + message.channel.mention,
            COLOR_YELLOW,
            [("👤 Usuario", message.author.mention, True),
             ("🔗 Link", urls[0][:100], False),
             ("⚠️ Warns", str(warn_count), True),
             ("📍 Canal", message.channel.mention, True)])
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
                     ("⚠️ Warns", str(warn_count) + "/5", True),
                     ("📍 Canal", message.channel.mention, True)]), delete_after=10)
                await self._dm(message.author, "🔗 INVITE BLOQUEADO",
                    "Tu mensaje fue eliminado en **" + message.guild.name + "** por contener un link de invitacion.",
                    COLOR_RED,
                    [("📍 Canal", "#" + message.channel.name, True),
                     ("🔗 Patron", pattern, False),
                     ("⚠️ Warns", str(warn_count) + "/5", True),
                     ("📝 Tu mensaje", message.content[:500], False),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                await self._alert_log(message.guild, "🔗 INVITE ELIMINADO",
                    message.author.mention + " envio un link de invitacion en " + message.channel.mention,
                    COLOR_RED,
                    [("👤 Usuario", message.author.mention, True),
                     ("🔗 Patron", pattern, False),
                     ("📍 Canal", message.channel.mention, True)])
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
                         ("📝 Tu mensaje", message.content[:500], False),
                         ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                    await self._alert_log(message.guild, "🎣 PHISHING BAN",
                        message.author.mention + " baneado por phishing",
                        COLOR_RED,
                        [("👤 Usuario", message.author.mention + "\n`" + str(message.author.id) + "`", True),
                         ("🔗 Link malicioso", url[:100], False),
                         ("⚡ Accion", "Ban automatico", True),
                         ("📍 Canal", message.channel.mention, True)])
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
            [("📝 Razon", reason, False),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
        await self._alert_log(message.guild, "🚫 NSFW BAN",
            message.author.mention + " baneado por contenido NSFW",
            COLOR_RED,
            [("👤 Usuario", message.author.mention + "\n`" + str(message.author.id) + "`", True),
             ("📝 Razon", reason, False),
             ("⚡ Accion", "Ban automatico", True),
             ("📍 Canal", message.channel.mention, True)])
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
                        COLOR_YELLOW,
                        [("👤 Usuario", message.author.mention, True),
                         ("📍 Canal", message.channel.mention, True),
                         ("📝 Mensaje", content[:300], False)])
                    await self._log(message.guild, "caps_blocked", message.author.id,
                                    details="Caps: " + str(int((caps / len(content)) * 100)) + "%")
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
                    await self._alert_log(message.guild, "🔨 BAN INMEDIATO - PALABRA EXTREMA",
                        message.author.mention + " baneado por palabra extrema: `" + word + "`",
                        COLOR_RED,
                        [("👤 Usuario", message.author.mention + "\n`" + str(message.author.id) + "`", True),
                         ("📝 Palabra", "`" + word + "`", True),
                         ("📍 Canal", message.channel.mention, True),
                         ("⚡ Accion", "Ban inmediato", True),
                         ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                    await self._log(message.guild, "banned_word_ban", message.author.id, details="EXTREMO: " + word)
                    return

                # Warn normal
                await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, "Palabra prohibida: " + word)
                warn_count = await db.get_warn_count(message.guild.id, message.author.id)

                # BAN por reincidencia
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
                    await self._alert_log(message.guild, "🔨 BAN - REINCIDENCIA",
                        message.author.mention + " baneado por " + str(warn_count) + " palabras prohibidas",
                        COLOR_RED,
                        [("👤 Usuario", message.author.mention + "\n`" + str(message.author.id) + "`", True),
                         ("🔢 Total", str(warn_count) + "/" + str(BAD_WORD_BAN_THRESHOLD), True),
                         ("📍 Canal", message.channel.mention, True),
                         ("⚡ Accion", "Ban automatico", True)])
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
                await self._alert_log(message.guild, "🚫 PALABRA PROHIBIDA",
                    message.author.mention + " uso una palabra prohibida en " + message.channel.mention,
                    COLOR_YELLOW,
                    [("👤 Usuario", message.author.mention, True),
                     ("📝 Palabra", "`" + word + "`", True),
                     ("⚠️ Warns", str(warn_count) + "/" + str(BAD_WORD_BAN_THRESHOLD), True),
                     ("📍 Canal", message.channel.mention, True)])
                await self._log(message.guild, "banned_word", message.author.id, details="Palabra: " + word)
                return

        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+", flags=re.UNICODE)
        if len(emoji_pattern.findall(content)) > MAX_EMOJI_COUNT:
            try:
                await message.delete()
                await self._alert_log(message.guild, "😀 EMOJIS BLOQUEADOS",
                    message.author.mention + " - exceso de emojis en " + message.channel.mention,
                    COLOR_YELLOW,
                    [("👤 Usuario", message.author.mention, True),
                     ("📍 Canal", message.channel.mention, True)])
                await self._log(message.guild, "emoji_spam", message.author.id, details="Exceso de emojis")
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

        inviter_text = str(inviter) + " (fue expulsado)" if inviter and not inviter.bot else "N/A"
        await self._alert_log(guild, "🤖 BOT NO AUTORIZADO",
            str(member) + " fue baneado (bot no autorizado)",
            COLOR_RED,
            [("🤖 Bot", str(member) + "\n`" + str(member.id) + "`", True),
             ("👤 Invitado por", inviter_text, True),
             ("⚡ Accion", "Ban del bot + kick del invitador", True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

        if inviter and not inviter.bot:
            try:
                await self._dm(inviter, "👢 EXPULSADO",
                    "Fuiste expulsado de **" + guild.name + "** por invitar un bot no autorizado.",
                    COLOR_RED,
                    [("🤖 Bot baneado", str(member), True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                await inviter.kick(reason="Invito bot no autorizado")
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

    async def _alert_log(self, guild, title, description, color, fields=None):
        """Envia un embed al canal de logs de seguridad"""
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(embed=create_embed(title, description, color, fields))
                except discord.Forbidden:
                    pass

    async def _log(self, guild, event_type, user_id=None, moderator_id=None, details=None):
        await db.add_log(guild.id, event_type, user_id, moderator_id, details)


async def setup(bot):
    await bot.add_cog(Security(bot))
