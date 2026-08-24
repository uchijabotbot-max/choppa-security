"""
cogs/behavior.py — Análisis de Comportamiento Avanzado
Detecta patrones sospechosos, scores de sospecha, cuentas nuevas
"""
import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
import time
from datetime import datetime, timedelta

from config import (
    SECURITY_ROLES, COLOR_RED, COLOR_GREEN, COLOR_YELLOW,
    COLOR_BLUE, COLOR_ORANGE, BOT_NAME, OWNER_ID
)
from utils.embeds import create_embed
from database import db


class Behavior(commands.Cog):
    """Análisis de comportamiento avanzado"""

    def __init__(self, bot):
        self.bot = bot
        self.message_times = defaultdict(lambda: defaultdict(list))
        self.join_times = defaultdict(list)
        self.suspicious_scores = defaultdict(lambda: defaultdict(int))

    # ==========================================
    #  EVENTOS
    # ==========================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        guild = member.guild
        now = time.time()

        # Track joins
        self.join_times[guild.id].append(now)
        self.join_times[guild.id] = [
            t for t in self.join_times[guild.id]
            if now - t < 3600  # 1 hora
        ]

        # Calcular score de sospecha
        score = 0
        reasons = []

        # Cuenta nueva
        account_age = (datetime.utcnow() - member.created_at).days
        if account_age < 7:
            score += 50
            reasons.append("Cuenta muy nueva (" + str(account_age) + " dias)")
        elif account_age < 14:
            score += 30
            reasons.append("Cuenta nueva (" + str(account_age) + " dias)")
        elif account_age < 30:
            score += 15
            reasons.append("Cuenta reciente (" + str(account_age) + " dias)")

        # Sin avatar
        if not member.avatar:
            score += 10
            reasons.append("Sin avatar personalizado")

        # Nombre sospechoso
        suspicious_names = ["raid", "nuke", "destroy", "hack", "exploit", "spam", "bot", "test", "alt", "token"]
        if any(s in member.name.lower() for s in suspicious_names):
            score += 25
            reasons.append("Nombre sospechoso")

        # Muchos joins recientes
        if len(self.join_times[guild.id]) > 10:
            score += 20
            reasons.append("Muchos joins recientes (" + str(len(self.join_times[guild.id])) + " en 1h)")

        # Guardar score
        self.suspicious_scores[guild.id][member.id] = score

        # Alertar si score alto
        if score >= 30:
            await self._alert_suspicious(member, guild, score, reasons)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        uid = message.author.id
        gid = message.guild.id
        now = time.time()

        # Track message patterns
        self.message_times[gid][uid].append(now)
        self.message_times[gid][uid] = [
            t for t in self.message_times[gid][uid]
            if now - t < 60  # 1 minuto
        ]

        # Detectar comportamiento sospechoso
        msg_count = len(self.message_times[gid][uid])
        if msg_count > 20:  # 20 mensajes en 1 minuto
            score = self.suspicious_scores[guild.id][uid]
            score += 15
            self.suspicious_scores[guild.id][uid] = score

            if score >= 50:
                await self._alert_message_flood(message, msg_count, score)

    # ==========================================
    #  COMANDOS
    # ==========================================

    @app_commands.command(name="behavior", description="Analisis de comportamiento de un usuario")
    @app_commands.describe(user="Usuario a analizar")
    async def behavior_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        if not self._check_role(interaction):
            return

        if not user:
            user = interaction.user

        score = self.suspicious_scores.get(interaction.guild.id, {}).get(user.id, 0)
        account_age = (datetime.utcnow() - user.created_at).days
        server_age = (datetime.utcnow() - user.joined_at).days if user.joined_at else 0

        # Analizar permisos
        dangerous_perms = []
        if user.guild_permissions:
            for perm, value in user.guild_permissions:
                if value and perm in ['administrator', 'ban_members', 'kick_members', 'manage_guild', 'manage_channels', 'manage_roles']:
                    dangerous_perms.append(perm)

        # Historial de warns
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)
        is_bl = await db.is_blacklisted(interaction.guild.id, user.id)
        is_wl = await db.is_whitelisted(interaction.guild.id, user.id)

        # Determinar nivel de riesgo
        if score >= 70:
            risk = "🔴 ALTO RIESGO"
            risk_color = COLOR_RED
        elif score >= 40:
            risk = "🟡 RIESGO MEDIO"
            risk_color = COLOR_YELLOW
        elif score >= 20:
            risk = "🟢 BAJO RIESGO"
            risk_color = COLOR_GREEN
        else:
            risk = "✅ SIN RIESGO"
            risk_color = COLOR_GREEN

        fields = [
            ("👤 Usuario", user.mention + "\n`" + str(user.id) + "`", True),
            ("📅 Cuenta creada", str(account_age) + " dias", True),
            ("📥 En el servidor", str(server_age) + " dias", True),
            ("🔍 Score de Sospecha", str(score) + "/100", True),
            ("⚠️ Nivel de Riesgo", risk, True),
            ("⚠️ Warns", str(warn_count), True),
            ("📋 Blacklist", "Si" if is_bl else "No", True),
            ("🛡️ Whitelist", "Si" if is_wl else "No", True),
        ]

        if dangerous_perms:
            fields.append(("🚨 Permisos Peligrosos", ", ".join(dangerous_perms), False))

        await interaction.response.send_message(embed=create_embed(
            "🔍 ANALISIS DE COMPORTAMIENTO",
            "Analisis completo de **" + user.name + "**",
            risk_color, fields))

    @app_commands.command(name="suspicious", description="Ver usuarios sospechosos del servidor")
    async def suspicious_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return

        guild = interaction.guild
        suspicious = []

        for member in guild.members:
            if member.bot:
                continue
            score = self.suspicious_scores.get(guild.id, {}).get(member.id, 0)
            if score >= 20:
                suspicious.append((member, score))

        suspicious.sort(key=lambda x: x[1], reverse=True)

        if not suspicious:
            return await interaction.response.send_message(embed=create_embed(
                "🔍 SOSPECHOSOS",
                "No hay usuarios sospechosos en este momento.",
                COLOR_GREEN))

        lines = []
        for member, score in suspicious[:15]:
            risk = "🔴" if score >= 70 else ("🟡" if score >= 40 else "🟢")
            lines.append(risk + " " + member.mention + " — Score: **" + str(score) + "**")

        await interaction.response.send_message(embed=create_embed(
            "🔍 USUARIOS SOSPECHOSOS",
            "\n".join(lines),
            COLOR_ORANGE,
            [("👥 Total", str(len(suspicious)), True)]))

    @app_commands.command(name="score", description="Ver score de sospecha de un usuario")
    @app_commands.describe(user="Usuario")
    async def score_cmd(self, interaction: discord.Interaction, user: discord.Member):
        if not self._check_role(interaction):
            return

        score = self.suspicious_scores.get(interaction.guild.id, {}).get(user.id, 0)

        if score >= 70:
            bar = "🔴🔴🔴🔴🔴"
            risk = "ALTO RIESGO"
        elif score >= 50:
            bar = "🟡🟡🟡🟡⚪"
            risk = "RIESGO MEDIO-ALTO"
        elif score >= 30:
            bar = "🟡🟡🟡⚪⚪"
            risk = "RIESGO MEDIO"
        elif score >= 10:
            bar = "🟢🟢⚪⚪⚪"
            risk = "BAJO RIESGO"
        else:
            bar = "🟢⚪⚪⚪⚪"
            risk = "SIN RIESGO"

        await interaction.response.send_message(embed=create_embed(
            "🔍 SCORE DE SOSPECHA",
            "Score de **" + user.name + "**",
            COLOR_BLUE if score < 30 else COLOR_ORANGE,
            [("👤 Usuario", user.mention, True),
             ("📊 Score", str(score) + "/100", True),
             ("⚠️ Riesgo", risk, True),
             ("📈 Barra", bar, False)]))

    @app_commands.command(name="patterns", description="Ver patrones de actividad del servidor")
    async def patterns_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return

        guild = interaction.guild

        # Analizar actividad
        total_members = guild.member_count
        suspicious_count = sum(1 for m in guild.members if not m.bot and
                              self.suspicious_scores.get(guild.id, {}).get(m.id, 0) >= 20)

        # Top posters (simulado)
        recent_joins = len([m for m in guild.members if m.joined_at and
                           (datetime.utcnow() - m.joined_at).days < 7])

        # Roles más usados
        role_counts = {}
        for member in guild.members:
            if not member.bot:
                for role in member.roles:
                    if role.name != "@everyone":
                        role_counts[role.name] = role_counts.get(role.name, 0) + 1

        top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        roles_text = "\n".join([r[0] + ": " + str(r[1]) + " miembros" for r in top_roles]) or "Ninguno"

        await interaction.response.send_message(embed=create_embed(
            "📊 PATRONES DE ACTIVIDAD",
            "Analisis de actividad del servidor **" + guild.name + "**",
            COLOR_BLUE,
            [("👥 Miembros totales", str(total_members), True),
             ("🆕 Nuevos (7 dias)", str(recent_joins), True),
             ("🔍 Sospechosos", str(suspicious_count), True),
             ("🎭 Roles mas usados", roles_text, False),
             ("📊 Servidores del bot", str(len(self.bot.guilds)), True)]))

    # ==========================================
    #  UTILIDADES
    # ==========================================

    async def _alert_suspicious(self, member, guild, score, reasons):
        """Alerta cuando un usuario tiene score alto"""
        await self._alert_log(guild, "🔍 USUARIO SOSPECHOSO",
            member.mention + " tiene un score de sospecha de **" + str(score) + "**",
            COLOR_ORANGE,
            [("👤 Usuario", member.mention + "\n`" + str(member.id) + "`", True),
             ("📊 Score", str(score) + "/100", True),
             ("📝 Razones", "\n".join(reasons), False),
             ("📅 Cuenta", str((datetime.utcnow() - member.created_at).days) + " dias", True)])

    async def _alert_message_flood(self, message, count, score):
        """Alerta cuando un usuario envia muchos mensajes"""
        await self._alert_log(message.guild, "📢 FLOOD DE MENSAJES",
            message.author.mention + " envio **" + str(count) + "** mensajes en 1 minuto",
            COLOR_YELLOW,
            [("👤 Usuario", message.author.mention, True),
             ("🔢 Mensajes", str(count) + " en 1 minuto", True),
             ("📊 Score", str(score) + "/100", True),
             ("📍 Canal", message.channel.mention, True)])

    async def _alert_log(self, guild, title, description, color, fields=None):
        """Envia embed al canal de logs"""
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(embed=create_embed(title, description, color, fields))
                except discord.Forbidden:
                    pass

    def _check_role(self, interaction):
        if any(r.name in SECURITY_ROLES for r in interaction.user.roles):
            return True
        import asyncio
        asyncio.get_event_loop().create_task(
            interaction.response.send_message(
                embed=create_embed("❌ Sin permisos", "Necesitas un rol de moderador.", COLOR_RED),
                ephemeral=True))
        return False


async def setup(bot):
    await bot.add_cog(Behavior(bot))
