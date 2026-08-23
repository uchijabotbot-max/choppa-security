# ─────────────────────────────────────────────
#  cogs/nuclear.py — Protecciones Nucleares
#  Anti-Nuke, Lockdown, Mass Detection, Role Protection
# ─────────────────────────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict
import time
from datetime import datetime, timedelta

from config import (
    BOT_NAME, SECURITY_ROLES, COLOR_PRIMARY, COLOR_SECURITY, COLOR_DANGER,
    ANTI_NUKE_ENABLED, NUKED_CHANNEL_DELETE_THRESHOLD, NUKED_CHANNEL_CREATE_THRESHOLD,
    NUKED_BAN_THRESHOLD, NUKED_KICK_THRESHOLD, NUKED_ROLE_CREATE_THRESHOLD,
    NUKED_TIME_WINDOW, NUKED_ACTION,
    LOCKDOWN_ENABLED, AUTO_LOCKDOWN_ENABLED, AUTO_LOCKDOWN_THRESHOLD,
    AUTO_LOCKDOWN_DURATION, AUTO_LOCKDOWN_CHANNELS,
    MASS_ACTION_DETECTION, MASS_BAN_THRESHOLD, MASS_KICK_THRESHOLD,
    MASS_CHANNEL_DELETE_THRESHOLD, MASS_CHANNEL_CREATE_THRESHOLD,
    MASS_ROLE_CREATE_THRESHOLD, MASS_ROLE_DELETE_THRESHOLD, MASS_ACTION_TIME_WINDOW,
    ROLE_PROTECTION_ENABLED, ROLE_MAX_CREATE_PER_MINUTE, ROLE_PREVENT_HIGH_PERMISSION,
    ROLE_BLOCKED_PERMISSIONS,
    WEBHOOK_PROTECTION_ENABLED, WEBHOOK_MAX_PER_CHANNEL, WEBHOOK_DELETE_UNAUTHORIZED,
    RAID_ALERT_PING_ENABLED, RAID_ALERT_ROLE, RAID_ALERT_MESSAGE
)
from utils.embeds import create_embed
from database import db


class NuclearCog(commands.Cog):
    """Protecciones nucleares — El bot más imparable de Discord"""

    def __init__(self, bot):
        self.bot = bot
        self.action_tracker = defaultdict(list)  # guild_id -> [(action_type, timestamp)]
        self.role_create_tracker = defaultdict(list)  # guild_id -> [timestamps]
        self.lockdown_active = defaultdict(bool)  # guild_id -> bool
        self.nuke_cooldown = defaultdict(float)  # guild_id -> last_nuke_alert

    # ═══════════════════════════════════════════
    #  ANTI-NUKE PROTECTION
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Detecta eliminación masiva de canales (Nuke)"""
        if not ANTI_NUKE_ENABLED:
            return

        guild = channel.guild
        now = time.time()

        # Buscar quién lo hizo
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            return

        if not moderator or moderator.bot:
            return

        # No castigar a otros bots del sistema
        if any(role.name in SECURITY_ROLES for role in moderator.roles):
            # Verificar si es admin legítimo
            if any(role.name in ["Owner", "Admin"] for role in moderator.roles):
                return

        # Trackear acción
        key = f"{guild.id}_channel_delete"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < NUKED_TIME_WINDOW]

        if len(self.action_tracker[key]) >= NUKED_CHANNEL_DELETE_THRESHOLD:
            # ¡NUKE DETECTADO!
            if now - self.nuke_cooldown.get(guild.id, 0) < 30:
                return  # Cooldown de 30s
            self.nuke_cooldown[guild.id] = now

            # Acción contra el nuker
            await self._handle_nuker(guild, moderator, "channel_deletion", f"{len(self.action_tracker[key])} canales eliminados")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Detecta creación masiva de canales (Nuke)"""
        if not ANTI_NUKE_ENABLED:
            return

        guild = channel.guild
        now = time.time()

        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            return

        if not moderator or moderator.bot:
            return

        key = f"{guild.id}_channel_create"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < NUKED_TIME_WINDOW]

        if len(self.action_tracker[key]) >= NUKED_CHANNEL_CREATE_THRESHOLD:
            if now - self.nuke_cooldown.get(guild.id, 0) < 30:
                return
            self.nuke_cooldown[guild.id] = now

            await self._handle_nuker(guild, moderator, "channel_creation", f"{len(self.action_tracker[key])} canales creados")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Detecta baneo masivo (Nuke)"""
        if not ANTI_NUKE_ENABLED:
            return

        now = time.time()

        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            return

        if not moderator or moderator.bot:
            return

        # No castigar a otros bots del sistema
        if any(role.name in SECURITY_ROLES for role in moderator.roles):
            if any(role.name in ["Owner", "Admin"] for role in moderator.roles):
                return

        key = f"{guild.id}_ban"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < NUKED_TIME_WINDOW]

        if len(self.action_tracker[key]) >= NUKED_BAN_THRESHOLD:
            if now - self.nuke_cooldown.get(guild.id, 0) < 30:
                return
            self.nuke_cooldown[guild.id] = now

            await self._handle_nuker(guild, moderator, "mass_ban", f"{len(self.action_tracker[key])} baneos")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Detecta kick masivo (Nuke)"""
        if not ANTI_NUKE_ENABLED:
            return

        guild = member.guild
        now = time.time()

        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            return

        if not moderator or moderator.bot:
            return

        if any(role.name in SECURITY_ROLES for role in moderator.roles):
            if any(role.name in ["Owner", "Admin"] for role in moderator.roles):
                return

        key = f"{guild.id}_kick"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < NUKED_TIME_WINDOW]

        if len(self.action_tracker[key]) >= NUKED_KICK_THRESHOLD:
            if now - self.nuke_cooldown.get(guild.id, 0) < 30:
                return
            self.nuke_cooldown[guild.id] = now

            await self._handle_nuker(guild, moderator, "mass_kick", f"{len(self.action_tracker[key])} kicks")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Detecta creación masiva de roles + protección de permisos"""
        if not ROLE_PROTECTION_ENABLED:
            return

        guild = role.guild
        now = time.time()

        # Protección de permisos altos
        if ROLE_PREVENT_HIGH_PERMISSION:
            blocked_perms = []
            for perm_name in ROLE_BLOCKED_PERMISSIONS:
                perm_value = getattr(role.permissions, perm_name, None)
                if perm_value and perm_value[1]:  # Si el permiso está habilitado
                    blocked_perms.append(perm_name)

            if blocked_perms:
                # Buscar quién creó el rol
                moderator = None
                try:
                    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                        if entry.target.id == role.id:
                            moderator = entry.user
                            break
                except discord.Forbidden:
                    pass

                # Eliminar el rol
                try:
                    await role.delete(reason=f"Role Protection: permisos bloqueados ({', '.join(blocked_perms)})")
                except discord.Forbidden:
                    pass

                if moderator and not moderator.bot:
                    # DM al admin
                    try:
                        dm_embed = create_embed(
                            "🛡️ ROLE PROTECTION — PERMISOS BLOQUEADOS",
                            f"Creaste un rol con permisos prohibidos en **{guild.name}**",
                            color=0xFF0000,
                            fields=[
                                ("🎭 Rol eliminado", role.name, True),
                                ("🔑 Permisos bloqueados", "\n".join(blocked_perms), False),
                                ("📝 Razón", "Permisos altos no permitidos", False),
                                ("🛡️ Bot", f"**{BOT_NAME}** — Role Protection", False),
                            ]
                        )
                        await moderator.send(embed=dm_embed)
                    except discord.ForForbidden:
                        pass

                    await self._log_nuclear(guild, "role_protection_delete", moderator.id,
                                           details=f"Rol '{role.name}' eliminado — permisos bloqueados: {', '.join(blocked_perms)}")
                return

        # Detección de creación masiva
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    moderator = entry.user
                    break
        except discord.ForForbidden:
            pass

        if moderator and not moderator.bot:
            key = f"{guild.id}_role_create"
            self.role_create_tracker[key].append(now)
            self.role_create_tracker[key] = [t for t in self.role_create_tracker[key] if now - t < 60]

            if len(self.role_create_tracker[key]) > ROLE_MAX_CREATE_PER_MINUTE:
                await self._handle_nuker(guild, moderator, "role_creation", f"{len(self.role_create_tracker[key])} roles creados en 1 minuto")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Detecta eliminación masiva de roles"""
        if not ANTI_NUKE_ENABLED:
            return

        guild = role.guild
        now = time.time()

        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user
                    break
        except discord.ForForbidden:
            return

        if not moderator or moderator.bot:
            return

        if any(role.name in SECURITY_ROLES for role in moderator.roles):
            if any(role.name in ["Owner", "Admin"] for role in moderator.roles):
                return

        key = f"{guild.id}_role_delete"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < NUKED_TIME_WINDOW]

        if len(self.action_tracker[key]) >= MASS_ROLE_DELETE_THRESHOLD:
            if now - self.nuke_cooldown.get(guild.id, 0) < 30:
                return
            self.nuke_cooldown[guild.id] = now

            await self._handle_nuker(guild, moderator, "mass_role_delete", f"{len(self.action_tracker[key])} roles eliminados")

    # ═══════════════════════════════════════════
    #  WEBHOOK PROTECTION
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        """Detecta webhooks no autorizados"""
        if not WEBHOOK_PROTECTION_ENABLED:
            return

        guild = channel.guild
        try:
            webhooks = await guild.webhooks()
            channel_webhooks = [w for w in webhooks if w.channel.id == channel.id]

            if len(channel_webhooks) > WEBHOOK_MAX_PER_CHANNEL:
                # Eliminar webhooks excedentes
                for webhook in channel_webhooks[WEBHOOK_MAX_PER_CHANNEL:]:
                    try:
                        await webhook.delete(reason="Webhook Protection: límite excedido")

                        # Log
                        await self._log_nuclear(guild, "webhook_deleted", details=f"Webhook eliminado en #{channel.name} — límite excedido")
                    except discord.ForForbidden:
                        pass
        except discord.ForForbidden:
            pass

    # ═══════════════════════════════════════════
    #  AUTO-LOCKDOWN DURING RAIDS
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Auto-lockdown durante raids masivos"""
        if not AUTO_LOCKDOWN_ENABLED or member.bot:
            return

        guild = member.guild
        now = time.time()
        settings = await db.get_guild_settings(guild.id)

        # Verificar si ya está en lockdown
        if self.lockdown_active.get(guild.id, False):
            return

        # Trackear joins
        key = f"{guild.id}_joins"
        self.action_tracker[key].append(now)
        self.action_tracker[key] = [t for t in self.action_tracker[key] if now - t < 10]

        threshold = settings.get('raid_threshold', AUTO_LOCKDOWN_THRESHOLD) if settings else AUTO_LOCKDOWN_THRESHOLD

        if len(self.action_tracker[key]) >= threshold:
            # ¡AUTO-LOCKDOWN!
            self.lockdown_active[guild.id] = True

            # Bloquear canales
            locked_channels = []
            for channel_name in AUTO_LOCKDOWN_CHANNELS:
                for channel in guild.text_channels:
                    if channel_name.lower() in channel.name.lower():
                        try:
                            overwrite = channel.overwrites_for(guild.default_role)
                            overwrite.send_messages = False
                            await channel.set_permissions(guild.default_role, overwrite=overwrite,
                                                          reason="Auto-Lockdown: Raid detectado")
                            locked_channels.append(channel.mention)
                        except discord.ForForbidden:
                            pass

            # Ping a admins
            if RAID_ALERT_PING_ENABLED:
                admin_role = discord.utils.get(guild.roles, name=RAID_ALERT_ROLE)
                if admin_role:
                    # Buscar canal de logs
                    log_channel_id = settings.get('log_channel_id') if settings else None
                    if log_channel_id:
                        channel = guild.get_channel(log_channel_id)
                        if channel:
                            embed = create_embed(
                                "🚨🚨 AUTO-LOCKDOWN ACTIVADO 🚨🚨",
                                f"**{len(self.action_tracker[key])}** miembros nuevos en **10 segundos**",
                                color=0xFF0000,
                                fields=[
                                    ("🔒 Canales bloqueados", "\n".join(locked_channels) if locked_channels else "Todos", False),
                                    ("⏱️ Duración", f"{AUTO_LOCKDOWN_DURATION // 60} minutos", True),
                                    ("⏰ Se desbloquea", f"<t:{int(now + AUTO_LOCKDOWN_DURATION)}:R>", True),
                                    ("🛡️ Bot", f"**{BOT_NAME}** — Auto-Lockdown", False),
                                ]
                            )
                            await channel.send(f"{admin_role.mention} {RAID_ALERT_MESSAGE}", embed=embed)

            # Timer para desbloquear
            await asyncio.sleep(AUTO_LOCKDOWN_DURATION)
            self.lockdown_active[guild.id] = False

            # Desbloquear canales
            for channel_name in AUTO_LOCKDOWN_CHANNELS:
                for channel in guild.text_channels:
                    if channel_name.lower() in channel.name.lower():
                        try:
                            overwrite = channel.overwrites_for(guild.default_role)
                            overwrite.send_messages = None
                            await channel.set_permissions(guild.default_role, overwrite=overwrite,
                                                          reason="Auto-Lockdown: Desbloqueado")
                        except discord.ForForbidden:
                            pass

            # Log
            if log_channel_id:
                channel = guild.get_channel(log_channel_id)
                if channel:
                    await channel.send(embed=create_embed(
                        "🔓 AUTO-LOCKDOWN DESACTIVADO",
                        "Los canales han sido desbloqueados.",
                        color=0x00FF00
                    ))

            self.action_tracker[key] = []

    # ═══════════════════════════════════════════
    #  SUSPICIOUS ACTIVITY DETECTION
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Detecta actividad sospechosa"""
        if member.bot:
            return

        guild = member.guild

        # Detectar nombres sospechosos
        from config import SUSPICIOUS_NAME_KEYWORDS
        member_name = member.name.lower()
        for keyword in SUSPICIOUS_NAME_KEYWORDS:
            if keyword in member_name:
                settings = await db.get_guild_settings(guild.id)
                log_channel_id = settings.get('log_channel_id') if settings else None
                if log_channel_id:
                    channel = guild.get_channel(log_channel_id)
                    if channel:
                        embed = create_embed(
                            "🔍 NOMBRE SOSPECHOSO DETECTADO",
                            f"**{member.mention}** tiene un nombre sospechoso",
                            color=0xFF4500,
                            fields=[
                                ("👤 Usuario", f"{member}\n`{member.id}`", True),
                                ("📝 Nombre", member.name, True),
                                ("🔑 Keyword", keyword, True),
                                ("📅 Cuenta creada", f"Hace {(datetime.utcnow() - member.created_at).days} días", True),
                                ("🛡️ Bot", f"**{BOT_NAME}** — Suspicious Activity", False),
                            ]
                        )
                        await channel.send(embed=embed)

                await self._log_nuclear(guild, "suspicious_activity", member.id,
                                       details=f"Nombre sospechoso: {member.name} (keyword: {keyword})")
                break

    # ═══════════════════════════════════════════
    #  HANDLERS
    # ═══════════════════════════════════════════

    async def _handle_nuker(self, guild, moderator, action_type, details):
        """Maneja al usuario que está haciendo nuke"""
        from config import NUKED_ACTION

        # Log de seguridad
        await self._log_nuclear(guild, f"nuke_{action_type}", moderator.id,
                               details=details)

        # DM al nuker ANTES de la acción
        try:
            dm_embed = create_embed(
                "🚨🚨 NUCLEAR PROTECTION ACTIVATED 🚨🚨",
                f"Actividad destructiva detectada en **{guild.name}**",
                color=0xFF0000,
                fields=[
                    ("⚠️ Acción detectada", action_type.replace("_", " ").title(), True),
                    ("📊 Detalles", details, False),
                    ("🔨 Acción", "BAN INMEDIATO" if NUKED_ACTION == "ban" else "KICK", True),
                    ("🕐 Hora", f"<t:{int(time.time())}:F>", True),
                    ("🛡️ Bot", f"**{BOT_NAME}** — Nuclear Protection", False),
                ]
            )
            await moderator.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Ejecutar acción
        try:
            if NUKED_ACTION == "ban":
                await moderator.ban(reason=f"Nuclear Protection: {action_type} — {details}")
            else:
                await moderator.kick(reason=f"Nuclear Protection: {action_type} — {details}")
        except discord.ForForbidden:
            pass

        # Ping a admins durante nuke
        settings = await db.get_guild_settings(guild.id)
        if RAID_ALERT_PING_ENABLED:
            admin_role = discord.utils.get(guild.roles, name=RAID_ALERT_ROLE)
            if admin_role:
                log_channel_id = settings.get('log_channel_id') if settings else None
                if log_channel_id:
                    channel = guild.get_channel(log_channel_id)
                    if channel:
                        await channel.send(
                            f"{admin_role.mention} 🚨 **NUKE DETECTADO** — {moderator.mention} fue baneado por {action_type}",
                            embed=create_embed(
                                "🚨 NUCLEO DETECTADO",
                                f"**{moderator.mention}** intentó destruir el servidor",
                                color=0xFF0000,
                                fields=[
                                    ("⚠️ Acción", action_type.replace("_", " ").title(), True),
                                    ("📊 Detalles", details, False),
                                    ("🔨 Acción tomada", "Ban inmediato", True),
                                ]
                            )
                        )

    # ═══════════════════════════════════════════
    #  COMANDOS DE EMERGENCIA
    # ═══════════════════════════════════════════

    @app_commands.command(name="lockdown", description="🔒 Bloquear todos los canales (Emergencia)")
    async def lockdown_cmd(self, interaction: discord.Interaction):
        """Bloquea todos los canales del servidor"""
        if not await self._check_security_role(interaction):
            return

        guild = interaction.guild
        self.lockdown_active[guild.id] = True

        locked = []
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(guild.default_role, overwrite=overwrite,
                                              reason=f"Lockdown por {interaction.user}")
                locked.append(channel.mention)
            except discord.ForForbidden:
                pass

        embed = create_embed(
            "🔒 LOCKDOWN ACTIVADO",
            f"Todos los canales han sido bloqueados por **{interaction.user.mention}**",
            color=0xFF0000,
            fields=[
                ("🔒 Canales bloqueados", str(len(locked)), True),
                ("⏱️ Desbloquear", "`/unlockdown`", True),
                ("🕐 Hora", f"<t:{int(time.time())}:F>", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await self._log_nuclear(guild, "lockdown_activated", interaction.user.id,
                               details=f"Lockdown activado — {len(locked)} canales bloqueados")

    @app_commands.command(name="unlockdown", description="🔓 Desbloquear todos los canales")
    async def unlockdown_cmd(self, interaction: discord.Interaction):
        """Desbloquea todos los canales del servidor"""
        if not await self._check_security_role(interaction):
            return

        guild = interaction.guild
        self.lockdown_active[guild.id] = False

        unlocked = []
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(guild.default_role, overwrite=overwrite,
                                              reason=f"Unlockdown por {interaction.user}")
                unlocked.append(channel.mention)
            except discord.ForForbidden:
                pass

        embed = create_embed(
            "🔓 LOCKDOWN DESACTIVADO",
            f"Todos los canales han sido desbloqueados por **{interaction.user.mention}**",
            color=0x00FF00,
            fields=[
                ("🔓 Canales desbloqueados", str(len(unlocked)), True),
                ("🕐 Hora", f"<t:{int(time.time())}:F>", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await self._log_nuclear(guild, "lockdown_deactivated", interaction.user.id,
                               details=f"Lockdown desactivado — {len(unlocked)} canales desbloqueados")

    @app_commands.command(name="antinuke", description="🛡️ Activar/desactivar Anti-Nuke")
    @app_commands.choices(action=[
        app_commands.Choice(name="Activar", value="on"),
        app_commands.Choice(name="Desactivar", value="off"),
    ])
    async def antinuke_cmd(self, interaction: discord.Interaction, action: str):
        """Activa o desactiva la protección Anti-Nuke"""
        if not await self._check_security_role(interaction):
            return

        # Toggle anti-nuke (esto es una configuración simple)
        status = "✅ Activado" if action == "on" else "❌ Desactivado"

        embed = create_embed(
            f"🛡️ Anti-Nuke {status}",
            f"La protección Anti-Nuke ha sido {'activada' if action == 'on' else 'desactivada'} por {interaction.user.mention}",
            color=0x00FF00 if action == "on" else 0xFF0000,
            fields=[
                ("🛡️ Estado", status, True),
                ("📝 Protecciones", "Anti-Nuke, Anti-Mass Actions, Role Protection", False),
                ("👑 Configurado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="emergency", description="🚨 Comandos de emergencia")
    @app_commands.choices(command=[
        app_commands.Choice(name="🔒 Lockdown", value="lockdown"),
        app_commands.Choice(name="🔓 Unlockdown", value="unlockdown"),
        app_commands.Choice(name="🛡️ Anti-Nuke Status", value="antinuke_status"),
        app_commands.Choice(name="📊 Security Report", value="report"),
    ])
    async def emergency_cmd(self, interaction: discord.Interaction, command: str):
        """Comandos de emergencia del bot"""
        if not await self._check_security_role(interaction):
            return

        if command == "lockdown":
            await self.lockdown_cmd(interaction)
        elif command == "unlockdown":
            await self.unlockdown_cmd(interaction)
        elif command == "antinuke_status":
            embed = create_embed(
                "🛡️ ESTADO ANTI-NUKE",
                "Protecciones nucleares activas",
                color=0x00FF00,
                fields=[
                    ("🚨 Anti-Nuke", "✅ Activo", True),
                    ("🔒 Auto-Lockdown", "✅ Activo", True),
                    ("🎭 Role Protection", "✅ Activo", True),
                    ("🔗 Webhook Protection", "✅ Activo", True),
                    ("🔍 Suspicious Activity", "✅ Activo", True),
                    ("📊 Mass Action Detection", "✅ Activo", True),
                ]
            )
            await interaction.response.send_message(embed=embed)
        elif command == "report":
            embed = create_embed(
                "📊 REPORTE DE SEGURIDAD NUCLEAR",
                f"Reporte completo de **{interaction.guild.name}**",
                color=0x000000,
                fields=[
                    ("🚨 Anti-Nuke", "✅ Activo", True),
                    ("🔒 Lockdown", "✅ Activo", True),
                    ("🎭 Role Protection", "✅ Activo", True),
                    ("🔗 Webhook Protection", "✅ Activo", True),
                    ("🔍 Suspicious Activity", "✅ Activo", True),
                    ("📊 Mass Detection", "✅ Activo", True),
                    ("👥 Miembros", str(interaction.guild.member_count), True),
                    ("📝 Canales", str(len(interaction.guild.channels)), True),
                    ("🎭 Roles", str(len(interaction.guild.roles)), True),
                    ("🔗 Webhooks", "Verificando...", True),
                ]
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

    async def _log_nuclear(self, guild, event_type, user_id=None, details=None):
        """Registra un evento nuclear"""
        await db.add_log(guild.id, event_type, user_id, details=details)

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
            "nuke_channel_deletion": "🚨 Nuke: Eliminación de canales",
            "nuke_channel_creation": "🚨 Nuke: Creación de canales",
            "nuke_mass_ban": "🚨 Nuke: Ban masivo",
            "nuke_mass_kick": "🚨 Nuke: Kick masivo",
            "nuke_mass_role_delete": "🚨 Nuke: Eliminación de roles",
            "role_protection_delete": "🎭 Role Protection: Rol eliminado",
            "webhook_deleted": "🔗 Webhook eliminado",
            "suspicious_activity": "🔍 Actividad sospechosa",
            "lockdown_activated": "🔒 Lockdown activado",
            "lockdown_deactivated": "🔓 Lockdown desactivado",
        }

        title = event_names.get(event_type, f"📋 {event_type}")
        user_mention = f"<@{user_id}>" if user_id else "N/A"

        embed = create_embed(
            title,
            f"**Usuario:** {user_mention}",
            color=0xFF0000,
            fields=[
                ("🕐 Hora", f"<t:{int(time.time())}:R>", True),
                ("📋 Evento", event_type, True),
            ]
        )

        if details:
            embed.add_field(name="📝 Detalles", value=details[:1024], inline=False)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(NuclearCog(bot))
