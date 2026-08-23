# ─────────────────────────────────────────────
#  cogs/behavior.py — Análisis de Comportamiento
#  Detección avanzada de patrones sospechosos
# ─────────────────────────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict, Counter
import time
import re
from datetime import datetime, timedelta

from config import BOT_NAME, SECURITY_ROLES
from utils.embeds import create_embed
from database import db


class BehaviorCog(commands.Cog):
    """Análisis avanzado de comportamiento de usuarios"""

    def __init__(self, bot):
        self.bot = bot
        # Tracking de comportamiento
        self.message_patterns = defaultdict(list)    # user_id -> [timestamps]
        self.channel_activity = defaultdict(Counter) # user_id -> Counter(channel_id)
        self.mention_targets = defaultdict(Counter)  # user_id -> Counter(target_id)
        self.join_patterns = defaultdict(list)       # guild_id -> [timestamps]
        self.user_scores = defaultdict(float)        # user_id -> suspiciousness score
        self.warning_history = defaultdict(list)     # user_id -> [warnings]

    # ═══════════════════════════════════════════
    #  COMANDOS
    # ═══════════════════════════════════════════

    @app_commands.command(name="behavior", description="🔍 Analizar comportamiento de un usuario")
    @app_commands.describe(user="Usuario a analizar")
    async def analyze_behavior(self, interaction: discord.Interaction, user: discord.Member = None):
        """Análisis detallado de comportamiento de un usuario"""
        if not await self._check_security_role(interaction):
            return

        if user is None:
            user = interaction.user

        await interaction.response.defer()

        # Calcular score de sospecha
        score = await self._calculate_suspicion_score(user)
        factors = await self._get_suspicion_factors(user)

        # Determinar nivel de riesgo
        if score >= 80:
            risk = "🚨 CRÍTICO"
            risk_color = 0xFF0000
        elif score >= 60:
            risk = "⚠️ ALTO"
            risk_color = 0xFF4500
        elif score >= 40:
            risk = "🟡 MEDIO"
            risk_color = 0xFFFF00
        elif score >= 20:
            risk = "🟢 BAJO"
            risk_color = 0x00FF00
        else:
            risk = "✅ LIMPIO"
            risk_color = 0x00FF00

        embed = create_embed(
            f"🔍 ANÁLISIS DE COMPORTAMIENTO",
            f"Análisis de **{user.mention}**",
            color=risk_color,
            fields=[
                ("📊 Score de Sospecha", f"**{score}/100** — {risk}", False),
                ("📋 Factores", "\n".join(factors[:10]) if factors else "Ninguno detectado", False),
            ]
        )

        # Info adicional
        account_age = (datetime.utcnow() - user.created_at).days
        server_age = (datetime.utcnow() - user.joined_at).days if user.joined_at else 0

        embed.add_field(
            name="👤 Info del Usuario",
            value=(
                f"**Cuenta:** {account_age} días\n"
                f"**En servidor:** {server_age} días\n"
                f"**Warns:** {await db.get_warn_count(interaction.guild.id, user.id)}\n"
            ),
            inline=True
        )

        # Patrones detectados
        patterns = self._detect_patterns(user.id)
        if patterns:
            embed.add_field(
                name="📈 Patrones Detectados",
                value="\n".join(patterns[:5]),
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="suspicious", description="🚨 Ver usuarios sospechosos")
    @app_commands.describe(limit="Número de usuarios a mostrar")
    async def list_suspicious(self, interaction: discord.Interaction, limit: int = 10):
        """Muestra una lista de usuarios sospechosos"""
        if not await self._check_security_role(interaction):
            return

        await interaction.response.defer()

        suspicious_users = []

        for member in interaction.guild.members:
            if member.bot:
                continue

            score = await self._calculate_suspicion_score(member)
            if score > 30:  # Umbral de sospecha
                suspicious_users.append((member, score))

        suspicious_users.sort(key=lambda x: x[1], reverse=True)

        if not suspicious_users:
            embed = create_embed(
                "✅ Sin usuarios sospechosos",
                "No se detectaron usuarios sospechosos en el servidor.",
                color=0x00FF00
            )
            await interaction.followup.send(embed=embed)
            return

        user_list = []
        for member, score in suspicious_users[:limit]:
            if score >= 80:
                emoji = "🚨"
            elif score >= 60:
                emoji = "⚠️"
            elif score >= 40:
                emoji = "🟡"
            else:
                emoji = "🟢"

            user_list.append(
                f"{emoji} **{member.name}** — Score: {score}/100"
            )

        embed = create_embed(
            f"🚨 USUARIOS SOSPECHOSOS ({len(suspicious_users)} detectados)",
            "\n".join(user_list),
            color=0xFF4500,
            fields=[
                ("📊 Total", str(len(suspicious_users)), True),
                ("🔍 Analizados", str(interaction.guild.member_count), True),
            ]
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="score", description="📊 Ver score de sospecha de un usuario")
    @app_commands.describe(user="Usuario a consultar")
    async def check_score(self, interaction: discord.Interaction, user: discord.Member = None):
        """Muestra el score de sospecha de un usuario"""
        if user is None:
            user = interaction.user

        score = await self._calculate_suspicion_score(user)

        # Barra de progreso
        filled = int(score / 5)
        empty = 20 - filled
        bar = "█" * filled + "░" * empty

        if score >= 80:
            status = "🚨 CRÍTICO"
            color = 0xFF0000
        elif score >= 60:
            status = "⚠️ ALTO"
            color = 0xFF4500
        elif score >= 40:
            status = "🟡 MEDIO"
            color = 0xFFFF00
        elif score >= 20:
            status = "🟢 BAJO"
            color = 0x00FF00
        else:
            status = "✅ LIMPIO"
            color = 0x00FF00

        embed = create_embed(
            f"📊 SCORE: {user.name}",
            f"Score de sospecha de **{user.mention}**",
            color=color,
            fields=[
                ("📊 Score", f"**{score}/100**", True),
                ("📋 Estado", status, True),
                ("📈 Progreso", f"`{bar}` {score}%", False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="patterns", description="📈 Ver patrones de actividad del servidor")
    async def view_patterns(self, interaction: discord.Interaction):
        """Muestra patrones de actividad del servidor"""
        if not await self._check_security_role(interaction):
            return

        # Analizar actividad del servidor
        guild = interaction.guild

        # Horas más activas
        hour_activity = Counter()
        for member in guild.members:
            if member.joined_at:
                hour = member.joined_at.hour
                hour_activity[hour] += 1

        peak_hours = hour_activity.most_common(5)

        # Días más activos
        day_activity = Counter()
        for member in guild.members:
            if member.joined_at:
                day = member.joined_at.strftime("%A")
                day_activity[day] += 1

        peak_days = day_activity.most_common(3)

        # Distribución de cuentas nuevas
        recent_accounts = Counter()
        for member in guild.members:
            if not member.bot:
                age = (datetime.utcnow() - member.created_at).days
                if age < 7:
                    recent_accounts["< 7 días"] += 1
                elif age < 30:
                    recent_accounts["7-30 días"] += 1
                elif age < 90:
                    recent_accounts["1-3 meses"] += 1
                elif age < 365:
                    recent_accounts["3-12 meses"] += 1
                else:
                    recent_accounts["1+ años"] += 1

        embed = create_embed(
            "📈 PATRONES DE ACTIVIDAD",
            f"Análisis de patrones de **{guild.name}**",
            color=0x000000,
            fields=[
                ("⏰ Horas más activas", "\n".join([f"• {h}:00 — {c} joins" for h, c in peak_hours]), False),
                ("📅 Días más activos", "\n".join([f"• {d} — {c} joins" for d, c in peak_days]), False),
                ("👤 Distribución de cuentas", "\n".join([f"• {k}: {v}" for k, v in sorted(recent_accounts.items())]), False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  ANÁLISIS DE COMPORTAMIENTO
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message):
        """Analiza comportamiento en cada mensaje"""
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        now = time.time()

        # Trackear patrones de mensajes
        self.message_patterns[user_id].append(now)
        self.message_patterns[user_id] = [
            t for t in self.message_patterns[user_id] if now - t < 3600
        ]

        # Trackear actividad por canal
        self.channel_activity[user_id][message.channel.id] += 1

        # Trackear menciones
        for mentioned in message.mentions:
            self.mention_targets[user_id][mentioned.id] += 1

        # Actualizar score de sospecha
        await self._update_suspicion_score(message.author, message)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Analiza comportamiento al unirse"""
        if member.bot:
            return

        # Análisis de cuenta nueva
        account_age = (datetime.utcnow() - member.created_at).days

        if account_age < 3:
            # Cuenta muy nueva - alerta crítica
            self.user_scores[member.id] += 50
            await self._alert_suspicious_account(member, "cuenta_muy_nueva", f"Cuenta de {account_age} días")
        elif account_age < 7:
            self.user_scores[member.id] += 25
        elif account_age < 30:
            self.user_scores[member.id] += 10

        # Análisis de patrón de join
        now = time.time()
        guild_id = member.guild.id
        self.join_patterns[guild_id].append(now)
        self.join_patterns[guild_id] = [
            t for t in self.join_patterns[guild_id] if now - t < 60
        ]

        # Si muchos joins en poco tiempo
        if len(self.join_patterns[guild_id]) >= 5:
            self.user_scores[member.id] += 30
            await self._alert_suspicious_account(member, "patron_join", f"{len(self.join_patterns[guild_id])} joins en 60s")

    async def _calculate_suspicion_score(self, member):
        """Calcula el score de sospecha de un usuario"""
        score = self.user_scores.get(member.id, 0)

        # Factor 1: Edad de cuenta
        account_age = (datetime.utcnow() - member.created_at).days
        if account_age < 1:
            score += 50
        elif account_age < 7:
            score += 25
        elif account_age < 30:
            score += 10

        # Factor 2: Tiempo en servidor
        if member.joined_at:
            server_age = (datetime.utcnow() - member.joined_at).days
            if server_age < 1:
                score += 20

        # Factor 3: Número de roles
        if len(member.roles) <= 1:  # Solo @everyone
            score += 15

        # Factor 4: Warnings
        warn_count = 0
        try:
            warn_count = await db.get_warn_count(member.guild.id, member.id)
        except Exception:
            pass
        score += warn_count * 10

        # Factor 5: Patrones de actividad
        patterns = self._detect_patterns(member.id)
        score += len(patterns) * 5

        # Limitar a 100
        return min(100, int(score))

    async def _get_suspicion_factors(self, member):
        """Obtiene los factores de sospecha"""
        factors = []

        # Edad de cuenta
        account_age = (datetime.utcnow() - member.created_at).days
        if account_age < 1:
            factors.append("🚨 Cuenta de menos de 1 día")
        elif account_age < 7:
            factors.append("⚠️ Cuenta de menos de 7 días")
        elif account_age < 30:
            factors.append("🟡 Cuenta de menos de 30 días")

        # Tiempo en servidor
        if member.joined_at:
            server_age = (datetime.utcnow() - member.joined_at).days
            if server_age < 1:
                factors.append("🚨 Se unió hoy")
            elif server_age < 7:
                factors.append("⚠️ Se unió hace menos de 7 días")

        # Roles
        if len(member.roles) <= 1:
            factors.append("⚠️ Sin roles asignados")

        # Warnings
        try:
            warn_count = await db.get_warn_count(member.guild.id, member.id)
            if warn_count > 0:
                factors.append(f"⚠️ {warn_count} warnings")
        except Exception:
            pass

        # Patrones
        patterns = self._detect_patterns(member.id)
        factors.extend(patterns)

        # Score acumulado
        if self.user_scores.get(member.id, 0) > 50:
            factors.append("🚨 Score acumulado alto")

        return factors

    def _detect_patterns(self, user_id):
        """Detecta patrones sospechosos en la actividad"""
        patterns = []

        # Patrón 1: Mensajes muy rápidos
        timestamps = self.message_patterns.get(user_id, [])
        if len(timestamps) > 10:
            # Calcular intervalos
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            avg_interval = sum(intervals) / len(intervals) if intervals else 999
            if avg_interval < 2:  # Mensaje cada 2 segundos
                patterns.append("⚡ Envía mensajes muy rápido")

        # Patrón 2: Solo menciona a la misma persona
        mentions = self.mention_targets.get(user_id, Counter())
        if mentions:
            top_mention = mentions.most_common(1)
            if top_mention and top_mention[0][1] > 10:
                patterns.append(f"🎯 Menciona mucho a un usuario")

        # Patrón 3: Solo habla en un canal
        channels = self.channel_activity.get(user_id, Counter())
        if channels and len(channels) == 1:
            patterns.append("📍 Solo habla en un canal")

        # Patrón 4: Actividad nocturna (2am - 5am)
        current_hour = datetime.utcnow().hour
        if 2 <= current_hour <= 5:
            patterns.append("🌙 Activo en horario nocturno")

        return patterns

    async def _update_suspicion_score(self, member, message):
        """Actualiza el score de sospecha basado en el comportamiento"""
        content = message.content.lower()
        user_id = member.id

        # Actualizar score basado en contenido
        suspicious_words = ['hack', 'exploit', 'raid', 'nuke', 'ddos', 'bot', 'spam']
        for word in suspicious_words:
            if word in content:
                self.user_scores[user_id] += 10

        # Actualizar score basado en menciones
        if len(message.mentions) > 5:
            self.user_scores[user_id] += 15

        # Decay del score con el tiempo
        if self.user_scores[user_id] > 0:
            self.user_scores[user_id] *= 0.99  # Reduce 1% por mensaje

    async def _alert_suspicious_account(self, member, alert_type, details):
        """Envía alerta de cuenta sospechosa"""
        settings = await db.get_guild_settings(member.guild.id)
        if not settings:
            return

        log_channel_id = settings.get('log_channel_id')
        if not log_channel_id:
            return

        channel = member.guild.get_channel(log_channel_id)
        if not channel:
            return

        alert_titles = {
            "cuenta_muy_nueva": "🚨 CUENTA MUY NUEVA DETECTADA",
            "patron_join": "🚨 PATRÓN DE JOIN SOSPECHOSO",
        }

        embed = create_embed(
            alert_titles.get(alert_type, "⚠️ ALERTA DE COMPORTAMIENTO"),
            f"**{member.mention}** ha sido marcado como sospechoso",
            color=0xFF0000,
            fields=[
                ("👤 Usuario", f"{member}\n`{member.id}`", True),
                ("📋 Tipo", alert_type.replace("_", " ").title(), True),
                ("📝 Detalles", details, False),
                ("📅 Cuenta creada", f"Hace {(datetime.utcnow() - member.created_at).days} días", True),
                ("🛡️ Bot", f"**{BOT_NAME}** — Análisis de Comportamiento", False),
            ]
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

        # Log
        await db.add_log(
            member.guild.id, "behavior_alert",
            member.id,
            details=f"{alert_type}: {details}"
        )

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


async def setup(bot):
    await bot.add_cog(BehaviorCog(bot))
