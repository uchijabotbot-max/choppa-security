# ─────────────────────────────────────────────
#  cogs/audit.py — Auditoría Completa + Features Extra
#  ServerAudit, Invite Tracking, Zalgo, Self-Bot
# ─────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import re
import time

from config import (
    BOT_NAME, BOT_FOOTER, SECURITY_ROLES, COLOR_PRIMARY,
    COLOR_SECURITY, COLOR_SUCCESS, COLOR_WARNING, COLOR_INFO, COLOR_DANGER,
    BOT_IMAGE
)
from utils.embeds import create_embed
from database import db


class AuditCog(commands.Cog):
    """Auditoría completa del servidor + Features avanzadas"""

    def __init__(self, bot):
        self.bot = bot
        self.message_cache = defaultdict(list)  # channel_id -> [content hashes]
        self.invite_cache = {}  # guild_id -> {invite_code: uses}

    # ═══════════════════════════════════════════
    #  COMANDO PRINCIPAL: SERVER AUDIT
    # ═══════════════════════════════════════════

    @app_commands.command(name="serveraudit", description="📊 Auditoría completa del servidor — toda la información")
    async def server_audit(self, interaction: discord.Interaction):
        """Muestra TODA la información del servidor"""
        if not await self._check_mod_role(interaction):
            return

        guild = interaction.guild
        await interaction.response.defer()

        # ══════ INFO GENERAL ══════
        owner = guild.owner
        created = guild.created_at
        age_days = (datetime.utcnow() - created).days

        # ══════ MIEMBROS ══════
        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots_count = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status == discord.Status.online)
        idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
        dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
        offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
        streaming = sum(1 for m in guild.members if m.activities and any(a.type == discord.ActivityType.streaming for a in m.activities))

        # ══════ CUENTAS NUEVAS (últimas 24h) ══════
        recent_joins_24h = sum(
            1 for m in guild.members
            if m.joined_at and (datetime.utcnow() - m.joined_at).total_seconds() < 86400
        )
        recent_joins_7d = sum(
            1 for m in guild.members
            if m.joined_at and (datetime.utcnow() - m.joined_at).days < 7
        )

        # ══════ CUENTAS SOSPECHOSAS ══════
        suspicious_accounts = sum(
            1 for m in guild.members
            if not m.bot and (datetime.utcnow() - m.created_at).days < 7
        )

        # ══════ CANALES ══════
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        stage_channels = len(guild.stage_channels)
        forum_channels = len(guild.forums)
        total_channels = text_channels + voice_channels + stage_channels + forum_channels

        # ══════ ROLES ══════
        roles = len(guild.roles)
        hoisted_roles = sum(1 for r in guild.roles if r.hoist)
        colored_roles = sum(1 for r in guild.roles if r.color != discord.Color.default())

        # ══════ EMOJIS ══════
        emojis = len(guild.emojis)
        animated_emojis = sum(1 for e in guild.emojis if e.animated)
        static_emojis = emojis - animated_emojis

        # ══════ BOOSTS ══════
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count or 0

        # ══════ INVITACIONES ══════
        try:
            invites = await guild.invites()
            total_invites = len(invites)
            total_invite_uses = sum(inv.uses for inv in invites)
        except discord.Forbidden:
            total_invites = 0
            total_invite_uses = 0

        # ══════ VERIFICACIÓN ══════
        verification_level = str(guild.verification_level).split(".")[-1].title()
        explicit_content = str(guild.explicit_content_filter).split(".")[-1].title()
        mfa_level = "Requerido" if guild.mfa_level else "No requerido"

        # ══════ FUNCIONALIDADES ══════
        features = []
        if "COMMUNITY" in guild.features:
            features.append("Comunidad")
        if "PARTNERED" in guild.features:
            features.append("Partner")
        if "VERIFIED" in guild.features:
            features.append("Verificado")
        if "VANITY_URL" in guild.features:
            features.append("Vanity URL")
        if "BANNER" in guild.features:
            features.append("Banner")
        if "ANIMATED_ICON" in guild.features:
            features.append("Icono Animado")
        if "WELCOME_SCREEN_ENABLED" in guild.features:
            features.append("Welcome Screen")

        # ══════ SEGURIDAD ══════
        settings = await db.get_guild_settings(guild.id)
        warn_count_total = 0
        bl_count = 0
        wl_count = 0
        try:
            warns = await db.get_logs(guild.id, limit=1000)
            warn_count_total = sum(1 for l in warns if l[2] == "mod_warn")
            bl = await db.get_blacklist(guild.id)
            bl_count = len(bl)
            wl = await db.get_whitelist(guild.id)
            wl_count = len(wl)
        except Exception:
            pass

        # ══════ PRIMER EMBED: GENERAL ══════
        embed1 = create_embed(
            f"📊 AUDITORÍA COMPLETA — {guild.name}",
            f"Información completa del servidor verificada por **{BOT_NAME}**",
            color=0x000000,
            image=guild.icon.url if guild.icon else BOT_IMAGE
        )

        embed1.add_field(
            name="👑 INFORMACIÓN GENERAL",
            value=(
                f"**Nombre:** {guild.name}\n"
                f"**ID:** `{guild.id}`\n"
                f"**Dueño:** {owner.mention if owner else 'Desconocido'} (`{guild.owner_id}`)\n"
                f"**Creado:** <t:{int(created.timestamp())}:F>\n"
                f"**Antigüedad:** {age_days} días ({age_days // 365} años, {(age_days % 365) // 30} meses)\n"
                f"**Descripción:** {guild.description or 'Sin descripción'}\n"
                f"**Idioma:** {guild.preferred_locale}"
            ),
            inline=False
        )

        # ══════ SEGUNDO EMBED: MIEMBROS ══════
        embed2 = create_embed(
            "👥 ESTADÍSTICAS DE MIEMBROS",
            "Distribución completa de miembros del servidor",
            color=0x000000
        )

        embed2.add_field(
            name="📊 Resumen",
            value=(
                f"**Total:** {total}\n"
                f"**Humanos:** {humans}\n"
                f"**Bots:** {bots_count}\n"
            ),
            inline=True
        )

        embed2.add_field(
            name="🟢 Estado",
            value=(
                f"**En línea:** {online}\n"
                f"**Inactivo:** {idle}\n"
                f"**No molestar:** {dnd}\n"
                f"**Desconectado:** {offline}\n"
                f"**Transmitiendo:** {streaming}\n"
            ),
            inline=True
        )

        embed2.add_field(
            name="🕐 Actividad Reciente",
            value=(
                f"**Últimas 24h:** {recent_joins_24h} nuevos\n"
                f"**Últimos 7 días:** {recent_joins_7d} nuevos\n"
                f"**⚠️ Cuentas sospechosas (<7 días):** {suspicious_accounts}\n"
            ),
            inline=True
        )

        # ══════ TERCER EMBED: CANALES Y ROLES ══════
        embed3 = create_embed(
            "📁 CANALES, ROLES Y EMOJIS",
            "Estructura completa del servidor",
            color=0x000000
        )

        embed3.add_field(
            name="📁 Canales",
            value=(
                f"**Total:** {total_channels}\n"
                f"**Texto:** {text_channels}\n"
                f"**Voz:** {voice_channels}\n"
                f"**Categorías:** {categories}\n"
                f"**Foros:** {forum_channels}\n"
                f"**Escenarios:** {stage_channels}\n"
            ),
            inline=True
        )

        embed3.add_field(
            name="🎭 Roles",
            value=(
                f"**Total:** {roles}\n"
                f"**Con barra:** {hoisted_roles}\n"
                f"**Con color:** {colored_roles}\n"
            ),
            inline=True
        )

        embed3.add_field(
            name="😀 Emojis",
            value=(
                f"**Total:** {emojis}\n"
                f"**Estáticos:** {static_emojis}\n"
                f"**Animados:** {animated_emojis}\n"
                f"**Límite:** {guild.emoji_limit}\n"
            ),
            inline=True
        )

        # ══════ CUARTO EMBED: SEGURIDAD ══════
        embed4 = create_embed(
            "🛡️ SEGURIDAD Y CONFIGURACIÓN",
            "Configuración de seguridad del servidor",
            color=0xFF0000
        )

        embed4.add_field(
            name="🔒 Seguridad de Discord",
            value=(
                f"**Nivel de verificación:** {verification_level}\n"
                f"**Filtro de contenido:** {explicit_content}\n"
                f"**2FA:** {mfa_level}\n"
            ),
            inline=True
        )

        embed4.add_field(
            name="🛡️ Protecciones Activas",
            value=(
                f"**Anti-Raid:** {'✅' if settings and settings.get('anti_raid') else '❌'}\n"
                f"**Anti-Spam:** {'✅' if settings and settings.get('anti_spam') else '❌'}\n"
                f"**Anti-Phishing:** {'✅' if settings and settings.get('anti_phishing') else '❌'}\n"
                f"**Auto-Mod:** {'✅' if settings and settings.get('auto_mod') else '❌'}\n"
                f"**Logs:** {'✅' if settings and settings.get('logs_enabled') else '❌'}\n"
            ),
            inline=True
        )

        embed4.add_field(
            name="📊 Registros",
            value=(
                f"**Warnings totales:** {warn_count_total}\n"
                f"**Blacklist:** {bl_count} usuarios\n"
                f"**Whitelist:** {wl_count} usuarios\n"
            ),
            inline=True
        )

        # ══════ QUINTO EMBED: INVITACIONES ══════
        embed5 = create_embed(
            "🔗 INVITACIONES Y BOOSTS",
            "Estado de invitaciones y boosts del servidor",
            color=0x00BFFF
        )

        embed5.add_field(
            name="🔗 Invitaciones",
            value=(
                f"**Total:** {total_invites}\n"
                f"**Usos totales:** {total_invite_uses}\n"
            ),
            inline=True
        )

        embed5.add_field(
            name="🚀 Boosts",
            value=(
                f"**Nivel:** {boost_level}\n"
                f"**Boosts:** {boost_count}\n"
                f"**Beneficios:** Nivel {boost_level}\n"
            ),
            inline=True
        )

        if features:
            embed5.add_field(
                name="✨ Funcionalidades",
                value="\n".join([f"• {f}" for f in features]),
                inline=True
            )

        # ══════ SEXTO EMBED: TOP ROLES ══════
        role_counts = {}
        for member in guild.members:
            for role in member.roles:
                if role != guild.default_role and not role.managed:
                    role_counts[role.name] = role_counts.get(role.name, 0) + 1

        top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_roles_text = "\n".join([f"**{r}**: {c} miembros" for r, c in top_roles]) if top_roles else "N/A"

        embed6 = create_embed(
            "🎭 ROLES MÁS POPULARES",
            "Los roles con más miembros",
            color=0x000000,
            fields=[
                ("🏆 Top 10", top_roles_text, False),
            ]
        )

        # ══════ CANALES MÁS ACTIVOS ══════
        # (Estimado basado en miembros en canales de voz)
        active_voice = []
        for vc in guild.voice_channels:
            if len(vc.members) > 0:
                active_voice.append(f"**{vc.name}**: {len(vc.members)} miembros")

        if active_voice:
            embed6.add_field(
                name="🔊 Canales de Voz Activos",
                value="\n".join(active_voice[:10]),
                inline=False
            )

        # Enviar todos los embeds
        embeds = [embed1, embed2, embed3, embed4, embed5, embed6]
        await interaction.followup.send(embeds=embeds)

    # ═══════════════════════════════════════════
    #  COMANDO: WHOIS DETALLADO
    # ═══════════════════════════════════════════

    @app_commands.command(name="whois", description="🔍 Información ultra-detallada de un usuario")
    @app_commands.describe(user="Usuario a investigar")
    async def whois(self, interaction: discord.Interaction, user: discord.Member = None):
        """Investigación completa de un usuario"""
        if user is None:
            user = interaction.user

        # Info de cuenta
        account_age = (datetime.utcnow() - user.created_at).days
        server_age = (datetime.utcnow() - user.joined_at).days if user.joined_at else 0

        # Posición en la jerarquía
        position = user.top_role.position

        # Permisos
        all_perms = []
        if user.guild_permissions.administrator:
            all_perms.append("👑 Administrador (TODOS los permisos)")
        if user.guild_permissions.ban_members:
            all_perms.append("🔨 Banear miembros")
        if user.guild_permissions.kick_members:
            all_perms.append("👢 Expulsar miembros")
        if user.guild_permissions.manage_messages:
            all_perms.append("📝 Gestionar mensajes")
        if user.guild_permissions.manage_channels:
            all_perms.append("📁 Gestionar canales")
        if user.guild_permissions.manage_roles:
            all_perms.append("🎭 Gestionar roles")
        if user.guild_permissions.manage_guild:
            all_perms.append("🏠 Gestionar servidor")
        if user.guild_permissions.mention_everyone:
            all_perms.append("📢 Mencionar a todos")
        if user.guild_permissions.manage_webhooks:
            all_perms.append("🔗 Gestionar webhooks")

        # Estado
        status_emoji = {
            discord.Status.online: "🟢 En línea",
            discord.Status.idle: "🟡 Inactivo",
            discord.Status.dnd: "🔴 No molestar",
            discord.Status.offline: "⚫ Desconectado",
        }
        status = status_emoji.get(user.status, "❓ Desconocido")

        # Actividad
        activities = []
        if user.activities:
            for activity in user.activities:
                if activity.type == discord.ActivityType.playing:
                    activities.append(f"🎮 Jugando a **{activity.name}**")
                elif activity.type == discord.ActivityType.streaming:
                    activities.append(f"🔴 Transmitiendo **{activity.name}**")
                elif activity.type == discord.ActivityType.listening:
                    activities.append(f"🎧 Escuchando **{activity.name}**")
                elif activity.type == discord.ActivityType.watching:
                    activities.append(f"👀 Mirando **{activity.name}**")
                elif activity.type == discord.ActivityType.custom:
                    activities.append(f"💭 {activity.name}")

        # Seguridad
        is_bl = await db.is_blacklisted(interaction.guild.id, user.id)
        is_wl = await db.is_whitelisted(interaction.guild.id, user.id)
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)

        # Sospechoso?
        is_suspicious = account_age < 7

        # Embeb principal
        embed = create_embed(
            f"🔍 WHOIS: {user.name}",
            f"Investigación completa de **{user.mention}**",
            color=0xFF0000 if is_suspicious else (0x00FF00 if is_wl else 0x000000),
            image=user.avatar.url if user.avatar else None
        )

        embed.add_field(
            name="👤 Información del Usuario",
            value=(
                f"**Nombre:** {user}\n"
                f"**ID:** `{user.id}`\n"
                f"**Mención:** {user.mention}\n"
                f"**Bot:** {'Sí 🤖' if user.bot else 'No'}\n"
                f"**Nickname:** {user.nick or 'Sin nickname'}\n"
            ),
            inline=True
        )

        embed.add_field(
            name="📅 Fechas",
            value=(
                f"**Cuenta creada:** <t:{int(user.created_at.timestamp())}:R>\n"
                f"**Edad de cuenta:** {account_age} días\n"
                f"**Se unió:** <t:{int(user.joined_at.timestamp())}:R>\n" if user.joined_at else "**Se unió:** Desconocido\n"
                f"**En servidor:** {server_age} días\n"
            ),
            inline=True
        )

        embed.add_field(
            name="🎭 Estado",
            value=(
                f"**Estado:** {status}\n"
                f"**Rol más alto:** {user.top_role.mention}\n"
                f"**Posición:** #{position}/{len(interaction.guild.roles)}\n"
                f"**Color:** {str(user.color)}\n"
            ),
            inline=True
        )

        if activities:
            embed.add_field(
                name="🎯 Actividad",
                value="\n".join(activities[:5]),
                inline=False
            )

        # Roles
        roles = [r.mention for r in user.roles[1:]]
        if roles:
            embed.add_field(
                name=f"🎭 Roles ({len(roles)})",
                value=", ".join(roles[:20]) + ("..." if len(roles) > 20 else ""),
                inline=False
            )

        # Permisos
        if all_perms:
            embed.add_field(
                name="🔑 Permisos",
                value="\n".join(all_perms[:15]),
                inline=False
            )

        # Seguridad
        security_status = []
        if is_bl:
            security_status.append("黑名单 **BLACKLIST**")
        if is_wl:
            security_status.append("✅ **WHITELIST (Inmune)**")
        if warn_count > 0:
            security_status.append(f"⚠️ **{warn_count} warnings**")
        if is_suspicious:
            security_status.append(f"🔍 **CUENTA SOSPECHOSA** ({account_age} días)")
        if not security_status:
            security_status.append("✅ Limpio")

        embed.add_field(
            name="🛡️ Estado de Seguridad",
            value="\n".join(security_status),
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDO: MASS Audit
    # ═══════════════════════════════════════════

    @app_commands.command(name="massaudit", description="📊 Auditar múltiples usuarios de una vez")
    @app_commands.describe(limit="Número de usuarios a auditar")
    async def mass_audit(self, interaction: discord.Interaction, limit: int = 20):
        """Audita múltiples usuarios y encuentra sospechosos"""
        if not await self._check_mod_role(interaction):
            return

        await interaction.response.defer()

        guild = interaction.guild
        suspicious = []
        new_accounts = []
        bots = []
        admin_count = 0

        for member in guild.members[:limit]:
            account_age = (datetime.utcnow() - member.created_at).days

            if member.bot:
                bots.append(member)
            elif account_age < 7:
                suspicious.append((member, account_age))
            elif account_age < 30:
                new_accounts.append((member, account_age))

            if member.guild_permissions.administrator:
                admin_count += 1

        # Reporte
        embed = create_embed(
            f"📊 REPORTE DE AUDITORÍA MASIVA",
            f"Análisis de **{min(limit, guild.member_count)}** usuarios en **{guild.name}**",
            color=0xFF4500,
            fields=[
                ("🔍 Sospechosos", f"{len(suspicious)} usuarios con cuentas < 7 días", True),
                ("🆕 Cuentas nuevas", f"{len(new_accounts)} usuarios con cuentas < 30 días", True),
                ("🤖 Bots", f"{len(bots)} bots detectados", True),
                ("👑 Admins", f"{admin_count} administradores", True),
            ]
        )

        if suspicious:
            sus_list = "\n".join([f"• {m.mention} — {d} días" for m, d in suspicious[:10]])
            embed.add_field(name="⚠️ Top Sospechosos", value=sus_list, inline=False)

        await interaction.followup.send(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDO: INVITE TRACKER
    # ═══════════════════════════════════════════

    @app_commands.command(name="invites", description="🔗 Ver todas las invitaciones del servidor")
    async def view_invites(self, interaction: discord.Interaction):
        """Muestra todas las invitaciones y sus usos"""
        if not await self._check_mod_role(interaction):
            return

        try:
            invites = await interaction.guild.invites()
        except discord.Forbidden:
            embed = create_embed("❌ Error", "No tengo permisos para ver invitaciones.", color=0xFF0000)
            await interaction.response.send_message(embed=embed)
            return

        if not invites:
            embed = create_embed("🔗 Invitaciones", "No hay invitaciones activas.", color=0x00BFFF)
            await interaction.response.send_message(embed=embed)
            return

        invite_list = []
        for inv in sorted(invites, key=lambda x: x.uses, reverse=True)[:20]:
            inviter = inv.inviter
            inviter_name = str(inviter) if inviter else "Desconocido"
            max_uses = f"{inv.max_uses} usos" if inv.max_uses else "Ilimitado"
            expires = f"<t:{int(inv.expires_at.timestamp())}:R>" if inv.expires_at else "Nunca"
            invite_list.append(
                f"**{inv.code}** — {inv.uses} usos\n"
                f"  Canal: {inv.channel.mention} | Creador: {inviter_name}\n"
                f"  Límite: {max_uses} | Expira: {expires}"
            )

        embed = create_embed(
            f"🔗 Invitaciones ({len(invites)} activas)",
            "\n\n".join(invite_list[:10]),
            color=0x00BFFF,
            fields=[
                ("📊 Total", f"{len(invites)} invitaciones", True),
                ("👥 Usos totales", str(sum(inv.uses for inv in invites)), True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDO: SECURITY SCORE
    # ═══════════════════════════════════════════

    @app_commands.command(name="securityscore", description="🏆 Calificación de seguridad del servidor")
    async def security_score(self, interaction: discord.Interaction):
        """Calcula un score de seguridad del servidor"""
        guild = interaction.guild
        score = 0
        max_score = 100
        recommendations = []

        # Verificación (20 puntos)
        if guild.verification_level == discord.VerificationLevel.high:
            score += 20
        elif guild.verification_level == discord.VerificationLevel.medium:
            score += 15
            recommendations.append("Sube la verificación a nivel High")
        elif guild.verification_level == discord.VerificationLevel.low:
            score += 10
            recommendations.append("Sube la verificación a nivel High")
        else:
            recommendations.append("⚠️ La verificación está en None — ¡Riesgo alto!")

        # 2FA (15 puntos)
        if guild.mfa_level:
            score += 15
        else:
            recommendations.append("Activa 2FA para administradores")

        # Filtro de contenido (15 puntos)
        if guild.explicit_content_filter == discord.ContentFilter.all_members:
            score += 15
        elif guild.explicit_content_filter == discord.ContentFilter.no_role:
            score += 10
        else:
            recommendations.append("Activa el filtro de contenido para todos")

        # Protecciones del bot (50 puntos)
        settings = await db.get_guild_settings(guild.id)
        if settings:
            if settings.get('anti_raid'):
                score += 8
            else:
                recommendations.append("Activa Anti-Raid")
            if settings.get('anti_spam'):
                score += 8
            else:
                recommendations.append("Activa Anti-Spam")
            if settings.get('anti_phishing'):
                score += 8
            else:
                recommendations.append("Activa Anti-Phishing")
            if settings.get('auto_mod'):
                score += 8
            else:
                recommendations.append("Activa Auto-Mod")
            if settings.get('logs_enabled'):
                score += 8
            else:
                recommendations.append("Activa Logs de seguridad")
        else:
            recommendations.append("⚠️ No hay configuración de seguridad — ¡Configura el bot!")

        # Determinar calificación
        if score >= 90:
            grade = "🏆 S — INCREÍBLE"
            grade_color = 0xFFD700
        elif score >= 80:
            grade = "🥇 A — EXCELENTE"
            grade_color = 0x00FF00
        elif score >= 70:
            grade = "🥈 B — BUENO"
            grade_color = 0x00BFFF
        elif score >= 60:
            grade = "🥉 C — REGULAR"
            grade_color = 0xFFFF00
        elif score >= 40:
            grade = "⚠️ D — MALO"
            grade_color = 0xFF4500
        else:
            grade = "🚨 F — PELIGROSO"
            grade_color = 0xFF0000

        embed = create_embed(
            f"🏆 SECURITY SCORE: {guild.name}",
            f"Calificación de seguridad del servidor",
            color=grade_color,
            fields=[
                ("📊 Score", f"**{score}/{max_score}** puntos", True),
                ("🏆 Calificación", grade, True),
                ("📝 Recomendaciones", "\n".join(recommendations[:10]) if recommendations else "¡Todo perfecto! ✅", False),
            ]
        )

        # Barra de progreso visual
        filled = int(score / 2)
        empty = 50 - filled
        progress_bar = "█" * filled + "░" * empty
        embed.add_field(name="📈 Progreso", value=f"`{progress_bar}` {score}%", inline=False)

        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  COMANDO: PING ALL (con info)
    # ═══════════════════════════════════════════

    @app_commands.command(name="pingall", description="📢 Ping a todos los admins con reporte")
    @app_commands.reason(description="Razón del ping")
    async def ping_all(self, interaction: discord.Interaction, reason: str = "Reporte de seguridad"):
        """Envía un reporte de seguridad a todos los admins"""
        if not await self._check_mod_role(interaction):
            return

        guild = interaction.guild
        admins = [m for m in guild.members if m.guild_permissions.administrator and not m.bot]

        admin_mentions = " ".join([a.mention for a in admins[:20]])

        embed = create_embed(
            "📢 REPORTE DE SEGURIDAD",
            f"**{interaction.user.mention}** envió un reporte a los administradores",
            color=0xFF4500,
            fields=[
                ("📝 Razón", reason, False),
                ("👮 Enviado por", interaction.user.mention, True),
                ("👑 Admins", str(len(admins)), True),
                ("🕐 Hora", f"<t:{int(time.time())}:F>", True),
            ]
        )

        await interaction.response.send_message(f"{admin_mentions}\n\nEste es un reporte de seguridad.", embed=embed)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    async def _check_mod_role(self, interaction):
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


async def setup(bot):
    await bot.add_cog(AuditCog(bot))
