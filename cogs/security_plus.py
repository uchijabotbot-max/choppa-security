"""
cogs/security_plus.py — Features de Seguridad Adicionales v7
Auto-Backup on Raid, Permission Monitor, Role Monitor, Channel Monitor,
Bot Permission Checker, Anti-Nuke v3, Anti-Spam v2
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict
import time
import json
import os
from datetime import datetime, timedelta

from config import (
    SECURITY_ROLES, COLOR_RED, COLOR_GREEN, COLOR_YELLOW,
    COLOR_BLUE, COLOR_ORANGE, BOT_NAME, OWNER_ID
)
from utils.embeds import create_embed
from database import db


class SecurityPlus(commands.Cog):
    """Features de seguridad adicionales"""

    def __init__(self, bot):
        self.bot = bot
        self.permission_changes = defaultdict(list)
        self.role_changes = defaultdict(list)
        self.channel_changes = defaultdict(list)

    # ==========================================
    #  AUTO-BACKUP ON RAID
    # ==========================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        guild = member.guild

        # Check if this is a raid
        settings = await db.get_settings(guild.id) or {}
        now = time.time()

        # Track joins
        if not hasattr(self, '_join_tracker'):
            self._join_tracker = defaultdict(list)
        self._join_tracker[guild.id].append(now)
        self._join_tracker[guild.id] = [
            t for t in self._join_tracker[guild.id]
            if now - t < 5  # 5 seconds
        ]

        # If raid detected, trigger auto-backup
        if len(self._join_tracker[guild.id]) >= 3:  # 3 joins in 5s
            await self._auto_backup_on_raid(guild)
            self._join_tracker[guild.id] = []

    async def _auto_backup_on_raid(self, guild):
        """Backup automatico durante raid"""
        try:
            # Create backup
            data = {
                "guild_id": guild.id,
                "guild_name": guild.name,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "raid_backup",
                "channels": [],
                "roles": [],
            }

            for ch in guild.channels:
                data["channels"].append({
                    "id": ch.id,
                    "name": ch.name,
                    "type": str(ch.type),
                })

            for role in guild.roles:
                if role.name != "@everyone":
                    data["roles"].append({
                        "id": role.id,
                        "name": role.name,
                        "color": role.color.value,
                    })

            # Save backup
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups")
            os.makedirs(backup_dir, exist_ok=True)
            filename = "raid_backup_" + str(guild.id) + "_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json"
            filepath = os.path.join(backup_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Alert
            await self._alert_log(guild, "💾 AUTO-BACKUP RAID",
                "Backup automatico creado durante raid",
                COLOR_ORANGE,
                [("📁 Archivo", filename, False),
                 ("📝 Canales", str(len(data["channels"])), True),
                 ("🎭 Roles", str(len(data["roles"])), True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

            await db.add_log(guild.id, "raid_backup", details="Auto-backup: " + filename)
        except Exception as e:
            pass

    # ==========================================
    #  PERMISSION MONITOR
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        """Monitorea cambios de permisos en roles"""
        if before.permissions == after.permissions:
            return

        # Detectar cambios peligrosos
        new_perms = [p for p, v in after.permissions if v and not before.permissions[p]]
        dangerous_perms = ["administrator", "ban_members", "kick_members", "manage_guild",
                          "manage_channels", "manage_roles", "manage_webhooks"]

        dangerous_new = [p for p in new_perms if p in dangerous_perms]

        if dangerous_new:
            await self._alert_log(after.guild, "🚨 PERMISOS PELIGROSOS AGREGADOS",
                "El rol **" + after.name + "** recibio permisos peligrosos",
                COLOR_RED,
                [("🎭 Rol", after.mention, True),
                 ("⚠️ Permisos", ", ".join(dangerous_new), False),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

    # ==========================================
    #  CHANNEL MONITOR
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Monitorea creacion de canales"""
        guild = channel.guild

        # Track channel creates
        now = time.time()
        if not hasattr(self, '_channel_create_tracker'):
            self._channel_create_tracker = defaultdict(list)
        self._channel_create_tracker[guild.id].append(now)
        self._channel_create_tracker[guild.id] = [
            t for t in self._channel_create_tracker[guild.id]
            if now - t < 5  # 5 seconds
        ]

        # If too many channels created, alert
        if len(self._channel_create_tracker[guild.id]) >= 3:
            await self._alert_log(guild, "🚨 CREACION MASIVA DE CANALES",
                str(len(self._channel_create_tracker[guild.id])) + " canales creados en 5 segundos",
                COLOR_RED,
                [("🔢 Canales", str(len(self._channel_create_tracker[guild.id])), True),
                 ("⚡ Accion", "Posible nuke detectado", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            self._channel_create_tracker[guild.id] = []

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Monitorea eliminacion de canales"""
        guild = channel.guild

        # Track channel deletes
        now = time.time()
        if not hasattr(self, '_channel_delete_tracker'):
            self._channel_delete_tracker = defaultdict(list)
        self._channel_delete_tracker[guild.id].append(now)
        self._channel_delete_tracker[guild.id] = [
            t for t in self._channel_delete_tracker[guild.id]
            if now - t < 5  # 5 seconds
        ]

        # If too many channels deleted, alert
        if len(self._channel_delete_tracker[guild.id]) >= 2:
            await self._alert_log(guild, "🚨 ELIMINACION MASIVA DE CANALES",
                str(len(self._channel_delete_tracker[guild.id])) + " canales eliminados en 5 segundos",
                COLOR_RED,
                [("🔢 Canales", str(len(self._channel_delete_tracker[guild.id])), True),
                 ("⚡ Accion", "Posible nuke detectado", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            self._channel_delete_tracker[guild.id] = []

    # ==========================================
    #  ROLE MONITOR
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Monitorea creacion de roles"""
        guild = role.guild
        now = time.time()

        # Track role creates
        if not hasattr(self, '_role_create_tracker'):
            self._role_create_tracker = defaultdict(list)
        self._role_create_tracker[guild.id].append(now)
        self._role_create_tracker[guild.id] = [
            t for t in self._role_create_tracker[guild.id]
            if now - t < 5  # 5 seconds
        ]

        # If too many roles created, alert
        if len(self._role_create_tracker[guild.id]) >= 3:
            await self._alert_log(guild, "🚨 CREACION MASIVA DE ROLES",
                str(len(self._role_create_tracker[guild.id])) + " roles creados en 5 segundos",
                COLOR_RED,
                [("🔢 Roles", str(len(self._role_create_tracker[guild.id])), True),
                 ("⚡ Accion", "Posible nuke detectado", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            self._role_create_tracker[guild.id] = []

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Monitorea eliminacion de roles"""
        guild = role.guild
        now = time.time()

        # Track role deletes
        if not hasattr(self, '_role_delete_tracker'):
            self._role_delete_tracker = defaultdict(list)
        self._role_delete_tracker[guild.id].append(now)
        self._role_delete_tracker[guild.id] = [
            t for t in self._role_delete_tracker[guild.id]
            if now - t < 5  # 5 seconds
        ]

        # If too many roles deleted, alert
        if len(self._role_delete_tracker[guild.id]) >= 2:
            await self._alert_log(guild, "🚨 ELIMINACION MASIVA DE ROLES",
                str(len(self._role_delete_tracker[guild.id])) + " roles eliminados en 5 segundos",
                COLOR_RED,
                [("🔢 Roles", str(len(self._role_delete_tracker[guild.id])), True),
                 ("⚡ Accion", "Posible nuke detectado", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
            self._role_delete_tracker[guild.id] = []

    # ==========================================
    #  BOT PERMISSION CHECKER
    # ==========================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Verifica permisos de bots al entrar"""
        if not member.bot:
            return

        guild = member.guild
        dangerous = []
        perms = member.guild_permissions

        if perms.administrator:
            dangerous.append("administrator")
        if perms.ban_members:
            dangerous.append("ban_members")
        if perms.kick_members:
            dangerous.append("kick_members")
        if perms.manage_guild:
            dangerous.append("manage_guild")
        if perms.manage_channels:
            dangerous.append("manage_channels")
        if perms.manage_roles:
            dangerous.append("manage_roles")
        if perms.manage_webhooks:
            dangerous.append("manage_webhooks")

        if dangerous:
            await self._alert_log(guild, "🤖 BOT CON PERMISOS PELIGROSOS",
                str(member) + " tiene permisos peligrosos",
                COLOR_RED,
                [("🤖 Bot", str(member) + "\n`" + str(member.id) + "`", True),
                 ("⚠️ Permisos", ", ".join(dangerous), False),
                 ("⚡ Accion", "Sera baneado automaticamente", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

    # ==========================================
    #  MASS MENTION ALERT
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Check for mass mentions
        total_mentions = len(message.mentions) + len(message.role_mentions)
        if total_mentions >= 5:  # 5+ mentions
            await self._alert_log(message.guild, "📢 MENCION MASIVA",
                message.author.mention + " menciono a **" + str(total_mentions) + "** personas",
                COLOR_ORANGE,
                [("👤 Autor", message.author.mention, True),
                 ("📢 Menciones", str(total_mentions), True),
                 ("📍 Canal", message.channel.mention, True),
                 ("📝 Mensaje", message.content[:300], False),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

    # ==========================================
    #  ANTI-NUKE V3
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        """Detecta cambios peligrosos en el servidor"""
        changes = []

        # Verificacion
        if before.verification_level != after.verification_level:
            changes.append("Verificacion: " + str(before.verification_level) + " -> " + str(after.verification_level))

        # Boost
        if before.premium_tier != after.premium_tier:
            changes.append("Boost: " + str(before.premium_tier) + " -> " + str(after.premium_tier))

        # Filtro de contenido
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append("Filtro de contenido cambiado")

        # Notificaciones
        if before.default_notifications != after.default_notifications:
            changes.append("Notificaciones cambiadas")

        if changes:
            await self._alert_log(after.guild, "⚙️ SERVIDOR MODIFICADO",
                "Configuracion del servidor fue modificada",
                COLOR_ORANGE,
                [("📝 Cambios", "\n".join(changes), False),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

    # ==========================================
    #  ANTI-VOICE RAID V2
    # ==========================================

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        # Track voice joins
        if before.channel is None and after.channel:
            now = time.time()
            if not hasattr(self, '_voice_tracker'):
                self._voice_tracker = defaultdict(list)
            self._voice_tracker[member.guild.id].append(now)
            self._voice_tracker[member.guild.id] = [
                t for t in self._voice_tracker[member.guild.id]
                if now - t < 5  # 5 seconds
            ]

            # If too many voice joins, alert
            if len(self._voice_tracker[member.guild.id]) >= 5:
                await self._alert_log(member.guild, "🔊 VOICE RAID DETECTADO",
                    str(len(self._voice_tracker[member.guild.id])) + " usuarios conectados a voz en 5 segundos",
                    COLOR_RED,
                    [("👥 Usuarios", str(len(self._voice_tracker[member.guild.id])), True),
                     ("⏱️ Ventana", "5s", True),
                     ("⚡ Accion", "Monitoreo intensivo activado", True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])
                self._voice_tracker[member.guild.id] = []

    # ==========================================
    #  ANTI-INTEGRATION V2
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        """Detecta nuevas integraciones/app"""
        try:
            integrations = await guild.integrations()
            for integration in integrations:
                app_name = integration.name
                app_type = type(integration).__name__

                await self._alert_log(guild, "🔌 NUEVA INTEGRACION DETECTADA",
                    "Se detecto una nueva integracion: **" + app_name + "**",
                    COLOR_ORANGE,
                    [("📦 Aplicacion", app_name, True),
                     ("📋 Tipo", app_type, True),
                     ("📍 Servidor", guild.name, True),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True),
                     ("⚠️ Nota", "Monitoreada por seguridad", False)])
                await db.add_log(guild.id, "integration_detected", details="App: " + app_name + " | Tipo: " + app_type)
        except:
            pass

    # ==========================================
    #  ANTI-EMOJI RAID
    # ==========================================

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        if added and len(added) >= 3:
            await self._alert_log(guild, "😀 EMOJI RAID DETECTADO",
                str(len(added)) + " emojis agregados de una vez",
                COLOR_RED,
                [("😀 Emojis", str(len(added)), True),
                 ("⚡ Accion", "Posible ataque de emojis", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

        if removed and len(removed) >= 3:
            await self._alert_log(guild, "😀 EMOJI DELETE RAID",
                str(len(removed)) + " emojis eliminados de una vez",
                COLOR_RED,
                [("😀 Emojis", str(len(removed)), True),
                 ("⚡ Accion", "Posible ataque de emojis", True),
                 ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)])

    # ==========================================
    #  UTILIDADES
    # ==========================================

    async def _alert_log(self, guild, title, description, color, fields=None):
        """Envia embed al canal de logs"""
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(embed=create_embed(title, description, color, fields))
                except:
                    pass


async def setup(bot):
    await bot.add_cog(SecurityPlus(bot))
