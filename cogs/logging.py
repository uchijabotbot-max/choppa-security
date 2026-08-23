# ─────────────────────────────────────────────
#  cogs/logging.py — Sistema de Logs Avanzado
#  Registro completo de actividad del servidor
# ─────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from utils.embeds import create_embed
from database import db


class LoggingCog(commands.Cog):
    """Sistema de logs avanzado para monitoreo de seguridad"""

    def __init__(self, bot):
        self.bot = bot

    # ═══════════════════════════════════════════
    #  COMANDOS DE LOGS
    # ═══════════════════════════════════════════

    @app_commands.command(name="logs", description="Ver logs recientes de seguridad")
    @app_commands.describe(limit="Número de logs a mostrar (máx 25)", event_type="Tipo de evento")
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Todos", value="all"),
        app_commands.Choice(name="Member Join", value="member_join"),
        app_commands.Choice(name="Member Leave", value="member_leave"),
        app_commands.Choice(name="Message Delete", value="message_delete"),
        app_commands.Choice(name="Message Edit", value="message_edit"),
        app_commands.Choice(name="Voice State", value="voice_state"),
        app_commands.Choice(name="Moderation", value="moderation"),
        app_commands.Choice(name="Security", value="security"),
    ])
    async def view_logs(self, interaction: discord.Interaction, limit: int = 10, event_type: str = "all"):
        """Muestra los logs de seguridad más recientes"""
        if not await self._check_mod_role(interaction):
            return

        # Obtener logs
        if event_type == "all":
            logs = await db.get_logs(interaction.guild.id, limit=min(limit, 25))
        elif event_type == "moderation":
            logs = await db.get_logs(interaction.guild.id, limit=min(limit, 25))
            logs = [l for l in logs if l[2].startswith("mod_")]
        elif event_type == "security":
            logs = await db.get_logs(interaction.guild.id, limit=min(limit, 25))
            logs = [l for l in logs if l[2] in ["raid_ban", "spam_mute", "phishing_detect", "blacklist_ban"]]
        else:
            logs = await db.get_logs(interaction.guild.id, limit=min(limit, 25), event_type=event_type)

        if not logs:
            embed = create_embed(
                "📋 Sin logs",
                "No hay logs recientes para mostrar.",
                color=0x00BFFF
            )
            await interaction.response.send_message(embed=embed, return_files=True)
            return

        # Crear embed con logs
        event_names = {
            "member_join": "📥 Member Join",
            "member_leave": "📤 Member Leave",
            "message_delete": "🗑️ Message Delete",
            "message_edit": "✏️ Message Edit",
            "voice_state": "🔊 Voice State",
            "spam_mute": "🔇 Spam Mute",
            "phishing_detect": "🎣 Phishing",
            "raid_ban": "🚨 Raid Ban",
            "blacklist_ban": "黑名单 Blacklist Ban",
            "mod_warn": "⚠️ Warn",
            "mod_ban": "🔨 Ban",
            "mod_kick": "👢 Kick",
            "mod_mute": "🔇 Mute",
            "mod_unban": "✅ Unban",
            "mod_unmute": "🔊 Unmute",
        }

        log_lines = []
        for log in logs:
            event = event_names.get(log[2], log[2])
            user_id = log[3]
            user_mention = f"<@{user_id}>" if user_id else "N/A"
            timestamp = log[6] if log[6] else "N/A"
            if hasattr(timestamp, 'strftime'):
                timestamp = timestamp.strftime("%H:%M:%S")

            log_lines.append(f"`{timestamp}` {event} — {user_mention}")

        embed = create_embed(
            f"📋 Logs de Seguridad ({len(logs)} entradas)",
            "\n".join(log_lines[:20]),
            color=0x00BFFF,
            fields=[
                ("📊 Total", f"{len(logs)} logs", True),
                ("🕐 Último", logs[0][6].strftime("%H:%M:%S UTC") if logs[0][6] else "N/A", True),
            ]
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlogchannel", description="Configurar canal de logs")
    @app_commands.describe(channel="Canal para logs de seguridad")
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Establece el canal donde se enviarán los logs de seguridad"""
        if not await self._check_mod_role(interaction):
            return

        await db.update_guild_settings(interaction.guild.id, log_channel_id=channel.id)

        embed = create_embed(
            "✅ Canal de logs configurado",
            f"Los logs de seguridad se enviarán a {channel.mention}",
            color=0x00FF00,
            fields=[
                ("📍 Canal", channel.mention, True),
                ("👑 Configurado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="securityinfo", description="Información completa de seguridad del servidor")
    async def security_info(self, interaction: discord.Interaction):
        """Muestra un reporte completo de seguridad"""
        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings:
            settings = await db.update_guild_settings(interaction.guild.id)
            settings = await db.get_guild_settings(interaction.guild.id)

        # Contar blacklist y whitelist
        bl = await db.get_blacklist(interaction.guild.id)
        wl = await db.get_whitelist(interaction.guild.id)

        # Contar warns activos (usuarios con warns)
        warns = await db.get_logs(interaction.guild.id, limit=100, event_type=None)
        warns_count = sum(1 for l in warns if l[2] == "mod_warn")

        # Contar bans recientes
        bans = await db.get_logs(interaction.guild.id, limit=100, event_type=None)
        bans_count = sum(1 for l in bans if l[2] == "mod_ban")

        embed = create_embed(
            "🛡️ REPORTE DE SEGURIDAD",
            f"Estado completo de seguridad de **{interaction.guild.name}**",
            color=0x000000,
            fields=[
                ("🚨 Anti-Raid", "✅ Activo" if settings.get('anti_raid') else "❌ Inactivo", True),
                ("🚫 Anti-Spam", "✅ Activo" if settings.get('anti_spam') else "❌ Inactivo", True),
                ("🎣 Anti-Phishing", "✅ Activo" if settings.get('anti_phishing') else "❌ Inactivo", True),
                ("📝 Auto-Mod", "✅ Activo" if settings.get('auto_mod') else "❌ Inactivo", True),
                ("📊 Logs", "✅ Activo" if settings.get('logs_enabled') else "❌ Inactivo", True),
                ("📋 Canal logs", f"<#{settings.get('log_channel_id')}>" if settings.get('log_channel_id') else "❌ No configurado", True),
                ("⛔ Blacklist", f"{len(bl)} usuarios", True),
                ("✅ Whitelist", f"{len(wl)} usuarios", True),
                ("⚠️ Warns activos", str(warns_count), True),
                ("🔨 Banes recientes", str(bans_count), True),
                ("👥 Miembros", str(interaction.guild.member_count), True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="usersecurity", description="Ver estado de seguridad de un usuario")
    @app_commands.describe(user="Usuario a revisar")
    async def user_security(self, interaction: discord.Interaction, user: discord.Member):
        """Muestra el estado de seguridad de un usuario específico"""
        if not await self._check_mod_role(interaction):
            return

        is_bl = await db.is_blacklisted(interaction.guild.id, user.id)
        is_wl = await db.is_whitelisted(interaction.guild.id, user.id)
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)
        warns = await db.get_warns(interaction.guild.id, user.id)

        # Info de la cuenta
        account_age = (datetime.utcnow() - user.created_at).days
        is_suspicious = account_age < 7

        # Estado del usuario
        if is_bl:
            status = "黑名单 BLACKLIST"
            status_color = 0xFF0000
        elif is_wl:
            status = "✅ WHITELIST"
            status_color = 0x00FF00
        elif warn_count > 0:
            status = f"⚠️ {warn_count} WARNINGS"
            status_color = 0xFFFF00
        elif is_suspicious:
            status = "🔍 SOSPECHOSO"
            status_color = 0xFF4500
        else:
            status = "✅ LIMPIO"
            status_color = 0x00FF00

        fields = [
            ("📋 Estado", status, True),
            ("👤 Usuario", user.mention, True),
            ("📅 Cuenta creada", f"Hace {account_age} días", True),
            ("⚠️ Sospechoso", "SÍ" if is_suspicious else "NO", True),
            ("⛔ Blacklist", "SÍ" if is_bl else "NO", True),
            ("✅ Whitelist", "SÍ" if is_wl else "NO", True),
            ("🔢 Total warns", str(warn_count), True),
        ]

        if warns:
            warn_list = []
            for i, w in enumerate(warns[:5], 1):
                warn_list.append(f"**{i}.** {w[4]}")
            fields.append(("📜 Últimos warns", "\n".join(warn_list), False))

        embed = create_embed(
            f"🔍 Seguridad: {user.name}",
            f"Reporte de seguridad de **{user.mention}**",
            color=status_color,
            fields=fields
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    async def _check_mod_role(self, interaction):
        """Verifica si el usuario tiene rol de moderador"""
        from config import SECURITY_ROLES
        has_role = any(role.name in SECURITY_ROLES for role in interaction.user.roles)
        if not has_role:
            embed = create_embed(
                "❌ Sin permisos",
                "Necesitas un rol de moderador para usar este comando.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True


async def setup(bot):
    await bot.add_cog(LoggingCog(bot))
