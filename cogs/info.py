# ─────────────────────────────────────────────
#  cogs/info.py — Comandos de Información v3
#  UserInfo, ServerInfo, Help, Ping, Whitelist
# ─────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
import platform
import psutil
from datetime import datetime

from config import BOT_NAME, BOT_VERSION, BOT_FOOTER, SECURITY_ROLES
from utils.embeds import (
    create_embed, userinfo_embed, serverinfo_embed, security_panel
)
from database import db


class InfoCog(commands.Cog):
    """Comandos de información del bot"""

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    @app_commands.command(name="help", description="Mostrar todos los comandos disponibles")
    async def help_command(self, interaction: discord.Interaction):
        """Muestra el panel de comandos"""
        embed = security_panel()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Ver latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        """Muestra la latencia del bot"""
        latency = round(self.bot.latency * 1000)
        if latency < 100:
            color = 0x00FF00
            status = "Excelente"
        elif latency < 200:
            color = 0xFFFF00
            status = "Buena"
        else:
            color = 0xFF0000
            status = "Mala"

        embed = create_embed(
            "🏓 Pong!",
            f"Latencia: **{latency}ms**",
            color=color,
            fields=[
                ("⏱️ Latencia", f"{latency}ms", True),
                ("📊 Estado", status, True),
                ("🤖 Bot", self.bot.user.name, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Información del bot")
    async def bot_info(self, interaction: discord.Interaction):
        """Muestra información detallada del bot"""
        uptime = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        process = psutil.Process()
        mem_usage = process.memory_info().rss / 1024 / 1024

        embed = create_embed(
            f"🤖 {BOT_NAME}",
            f"Bot de seguridad avanzado para Discord",
            color=0x000000,
            fields=[
                ("📋 Versión", BOT_VERSION, True),
                ("⏱️ Uptime", uptime_str, True),
                ("🏓 Ping", f"{round(self.bot.latency * 1000)}ms", True),
                ("🌐 Servidores", str(len(self.bot.guilds)), True),
                ("👥 Usuarios", str(len(self.bot.users)), True),
                ("💻 Python", platform.python_version(), True),
                ("📦 discord.py", discord.__version__, True),
                ("💾 Memoria", f"{mem_usage:.1f} MB", True),
                ("🖥️ Sistema", platform.system(), True),
                ("👑 Desarrollador", BOT_FOOTER, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Información de un usuario")
    @app_commands.describe(user="Usuario a consultar")
    async def user_info(self, interaction: discord.Interaction, user: discord.Member = None):
        """Muestra información detallada de un usuario"""
        if user is None:
            user = interaction.user

        embed = userinfo_embed(user)

        warn_count = await db.get_warn_count(interaction.guild.id, user.id)
        is_bl = await db.is_blacklisted(interaction.guild.id, user.id)
        is_wl = await db.is_whitelisted(interaction.guild.id, user.id)

        if warn_count > 0:
            embed.add_field(name="⚠️ Warns", value=str(warn_count), inline=True)
        if is_bl:
            embed.add_field(name="黑名单 Blacklist", value="SÍ", inline=True)
        if is_wl:
            embed.add_field(name="✅ Whitelist (Inmune)", value="SÍ", inline=True)

        key_perms = []
        if user.guild_permissions.administrator:
            key_perms.append("👑 Administrador")
        if user.guild_permissions.ban_members:
            key_perms.append("🔨 Banear")
        if user.guild_permissions.kick_members:
            key_perms.append("👢 Expulsar")
        if user.guild_permissions.manage_messages:
            key_perms.append("📝 Gestionar mensajes")
        if user.guild_permissions.manage_channels:
            key_perms.append("📁 Gestionar canales")

        if key_perms:
            embed.add_field(name="🔑 Permisos clave", value="\n".join(key_perms), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Información del servidor")
    async def server_info(self, interaction: discord.Interaction):
        """Muestra información detallada del servidor"""
        embed = serverinfo_embed(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="members", description="Estadísticas de miembros")
    async def member_stats(self, interaction: discord.Interaction):
        """Muestra estadísticas de miembros del servidor"""
        guild = interaction.guild
        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status == discord.Status.online)

        role_counts = {}
        for member in guild.members:
            for role in member.roles:
                if role != guild.default_role:
                    role_counts[role.name] = role_counts.get(role.name, 0) + 1

        top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_roles_text = "\n".join([f"**{role}**: {count}" for role, count in top_roles])

        embed = create_embed(
            f"👥 Estadísticas de {guild.name}",
            "Información detallada de miembros",
            color=0x000000,
            fields=[
                ("📊 Total", str(total), True),
                ("👤 Humanos", str(humans), True),
                ("🤖 Bots", str(bots), True),
                ("🟢 En línea", str(online), True),
                ("🎭 Roles más usados", top_roles_text if top_roles_text else "N/A", False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Información de un rol")
    @app_commands.describe(role="Rol a consultar")
    async def role_info(self, interaction: discord.Interaction, role: discord.Role):
        """Muestra información detallada de un rol"""
        member_count = sum(1 for m in interaction.guild.members if role in m.roles)

        perms = []
        if role.permissions.administrator:
            perms.append("👑 Administrador")
        if role.permissions.ban_members:
            perms.append("🔨 Banear miembros")
        if role.permissions.kick_members:
            perms.append("👢 Expulsar miembros")
        if role.permissions.manage_messages:
            perms.append("📝 Gestionar mensajes")
        if role.permissions.manage_channels:
            perms.append("📁 Gestionar canales")

        embed = create_embed(
            f"🎭 Información de {role.name}",
            f"Detalles del rol **{role.name}**",
            color=role.color if role.color != discord.Color.default() else 0x000000,
            fields=[
                ("📋 ID", f"`{role.id}`", True),
                ("🎨 Color", str(role.color), True),
                ("👥 Miembros", str(member_count), True),
                ("📍 Posición", str(role.position), True),
                ("🔑 Permisos", "\n".join(perms) if perms else "Sin permisos especiales", False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDOS DE ADMIN
    # ═══════════════════════════════════════════

    @app_commands.command(name="config", description="Ver configuración actual")
    async def view_config(self, interaction: discord.Interaction):
        """Muestra la configuración actual del bot"""
        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings:
            await db.update_guild_settings(interaction.guild.id)
            settings = await db.get_guild_settings(interaction.guild.id)

        embed = create_embed(
            f"⚙️ Configuración de {interaction.guild.name}",
            "Configuración actual del bot de seguridad",
            color=0x000000,
            fields=[
                ("🚨 Anti-Raid", "✅" if settings.get('anti_raid') else "❌", True),
                ("🚫 Anti-Spam", "✅" if settings.get('anti_spam') else "❌", True),
                ("🎣 Anti-Phishing", "✅" if settings.get('anti_phishing') else "❌", True),
                ("📝 Auto-Mod", "✅" if settings.get('auto_mod') else "❌", True),
                ("🔐 Verificación", "✅" if settings.get('verification') else "❌", True),
                ("📊 Logs", "✅" if settings.get('logs_enabled') else "❌", True),
                ("📍 Canal logs", f"<#{settings.get('log_channel_id')}>" if settings.get('log_channel_id') else "❌ No", True),
                ("📍 Canal verificación", f"<#{settings.get('verification_channel_id')}>" if settings.get('verification_channel_id') else "❌ No", True),
                ("🎭 Rol verificado", f"<@&{settings.get('verified_role_id')}>" if settings.get('verified_role_id') else "❌ No", True),
                ("🚨 Umbral raid", str(settings.get('raid_threshold', 5)), True),
                ("🚫 Umbral spam", str(settings.get('spam_threshold', 5)), True),
                ("🔇 Duración mute", f"{settings.get('mute_duration', 300)}s", True),
                ("⚠️ Warns → Kick", str(settings.get('warn_kick_threshold', 3)), True),
                ("🔨 Warns → Ban", str(settings.get('warn_ban_threshold', 5)), True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="toggle", description="Activar/desactivar sistema de seguridad")
    @app_commands.choices(system=[
        app_commands.Choice(name="Anti-Raid", value="anti_raid"),
        app_commands.Choice(name="Anti-Spam", value="anti_spam"),
        app_commands.Choice(name="Anti-Phishing", value="anti_phishing"),
        app_commands.Choice(name="Auto-Mod", value="auto_mod"),
        app_commands.Choice(name="Logs", value="logs_enabled"),
    ])
    async def toggle_system(self, interaction: discord.Interaction, system: str):
        """Activa o desactiva un sistema de seguridad"""
        if not await self._check_mod_role(interaction):
            return

        settings = await db.get_guild_settings(interaction.guild.id)
        current = settings.get(system, True) if settings else True
        new_value = 0 if current else 1

        await db.update_guild_settings(interaction.guild.id, **{system: new_value})

        status = "✅ Activado" if new_value else "❌ Desactivado"
        system_names = {
            'anti_raid': 'Anti-Raid', 'anti_spam': 'Anti-Spam',
            'anti_phishing': 'Anti-Phishing', 'auto_mod': 'Auto-Mod',
            'logs_enabled': 'Logs',
        }

        embed = create_embed(
            f"⚙️ {system_names.get(system, system)} {status}",
            f"El sistema ha sido {'activado' if new_value else 'desactivado'} por {interaction.user.mention}",
            color=0x00FF00 if new_value else 0xFF0000
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDO: OWNER / CREATOR
    # ═══════════════════════════════════════════

    @app_commands.command(name="owner", description="👑 Información del creador del bot")
    async def owner_info(self, interaction: discord.Interaction):
        """Muestra información del dueño/creador del bot"""
        from config import (
            OWNER_NAME, OWNER_ID, OWNER_STATUS, OWNER_BADGES,
            OWNER_DISCORD, OWNER_GITHUB, OWNER_BIO, OWNER_AVATAR,
            BOT_NAME, BOT_VERSION
        )

        # Intentar obtener el miembro real del servidor
        owner_member = None
        try:
            owner_member = interaction.guild.get_member(int(OWNER_ID)) if OWNER_ID.isdigit() else None
        except (ValueError, TypeError):
            pass

        # Si no se encuentra por ID, buscar por nombre
        if not owner_member:
            for member in interaction.guild.members:
                if member.name == OWNER_NAME or (member.nick and member.nick == OWNER_NAME):
                    owner_member = member
                    break

        # Crear embed principal
        embed = create_embed(
            f"👑 CREADOR DE {BOT_NAME.upper()}",
            f"Conoce al creador y desarrollador de **{BOT_NAME}**",
            color=0x000000,
            image=OWNER_AVATAR
        )

        embed.add_field(
            name="👤 Información Personal",
            value=(
                f"**Nombre:** {OWNER_NAME}\n"
                f"**Discord:** `{OWNER_DISCORD}`\n"
                f"**ID:** `{OWNER_ID}`\n"
                f"**Estado:** {OWNER_STATUS}\n"
            ),
            inline=True
        )

        embed.add_field(
            name="📊 Badges",
            value="\n".join([f"{b}" for b in OWNER_BADGES]),
            inline=True
        )

        embed.add_field(
            name="📝 Biografía",
            value=OWNER_BIO,
            inline=False
        )

        embed.add_field(
            name="🔗 Links",
            value=(
                f"**GitHub:** {OWNER_GITHUB}\n"
                f"**Discord:** {OWNER_DISCORD}\n"
            ),
            inline=True
        )

        embed.add_field(
            name="🤖 Sobre el Bot",
            value=(
                f"**Bot:** {BOT_NAME}\n"
                f"**Versión:** {BOT_VERSION}\n"
                f"**Creado por:** {OWNER_NAME}\n"
                f"**Propósito:** Proteger servidores de Discord con seguridad avanzada\n"
            ),
            inline=True
        )

        embed.add_field(
            name="🏆 Logros",
            value=(
                "• Creador del bot de seguridad más avanzado\n"
                "• Sistema Anti-Nuke, Anti-Raid, Anti-Phishing\n"
                "• Protecciones nucleares imparables\n"
                "• Moderación con DMs automáticos\n"
                "• Auditoría completa del servidor\n"
            ),
            inline=False
        )

        # Si el owner está en el servidor, mostrar info adicional
        if owner_member:
            embed.add_field(
                name="📍 En este Servidor",
                value=(
                    f"**Miembro:** {owner_member.mention}\n"
                    f"**Rol más alto:** {owner_member.top_role.mention}\n"
                    f"**Se unió:** <t:{int(owner_member.joined_at.timestamp())}:R>\n" if owner_member.joined_at else ""
                ),
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="creator", description="👑 Alternativa: Información del creador")
    async def creator_info(self, interaction: discord.Interaction):
        """Comando alternativo para ver info del creador"""
        await self.owner_info(interaction)

    @app_commands.command(name="creditos", description="🏆 Créditos del bot")
    async def credits(self, interaction: discord.Interaction):
        """Muestra los créditos y contribuidores del bot"""
        from config import OWNER_NAME, BOT_NAME, BOT_VERSION

        embed = create_embed(
            f"🏆 CRÉDITOS DE {BOT_NAME.upper()}",
            "Personas que hicieron posible este bot",
            color=0x000000,
            fields=[
                ("👑 Creador & Desarrollador", f"**{OWNER_NAME}** — Diseño, código y mantenimiento", False),
                ("🛡️ Seguridad", f"**{OWNER_NAME}** — Todos los sistemas de seguridad", False),
                ("🎨 Diseño", f"**{OWNER_NAME}** — Embeds y estilo visual", False),
                ("📊 Auditoría", f"**{OWNER_NAME}** — Sistema de auditoría completa", False),
                ("⚡ Features", f"**{OWNER_NAME}** — Anti-Nuke, Lockdown, Nuclear Protection", False),
                ("🤖 Bot", f"**{BOT_NAME}** v{BOT_VERSION}", True),
                ("📅 Año", "2026", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    async def _check_mod_role(self, interaction):
        """Verifica si el usuario tiene rol de moderador"""
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
    await bot.add_cog(InfoCog(bot))
