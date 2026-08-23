# ─────────────────────────────────────────────
#  cogs/canary.py — Canary Trap Anti-Infiltrados
#  Detecta infiltrados y moles en el servidor
# ─────────────────────────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
from collections import defaultdict
import time
import random
import hashlib
from datetime import datetime, timedelta

from config import BOT_NAME, SECURITY_ROLES
from utils.embeds import create_embed
from database import db


class CanaryCog(commands.Cog):
    """Sistema Canary Trap para detectar infiltrados"""

    def __init__(self, bot):
        self.bot = bot
        self.canary_links = {}  # guild_id -> {user_id: unique_link}
        self.canary_messages = defaultdict(list)  # guild_id -> [(user_id, message_content, timestamp)]
        self.leaked_users = defaultdict(set)  # guild_id -> {user_id}
        self.message_hashes = defaultdict(set)  # guild_id -> {hash}

    # ═══════════════════════════════════════════
    #  COMANDOS
    # ═══════════════════════════════════════════

    @app_commands.command(name="canary", description="🐦 Configurar Canary Trap")
    @app_commands.describe(channel="Canal donde se enviarán los enlaces canary")
    async def canary_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Configura el sistema Canary Trap en un canal"""
        if not await self._check_security_role(interaction):
            return

        guild_id = interaction.guild.id

        # Generar links únicos para cada miembro
        canary_links = {}
        for member in interaction.guild.members:
            if not member.bot:
                unique_code = self._generate_canary_code(member.id, guild_id)
                canary_links[member.id] = unique_code

        self.canary_links[guild_id] = canary_links

        # Enviar mensaje canary
        embed = create_embed(
            "🐦 CANARY TRAP ACTIVADO",
            "Este canal tiene protección contra filtraciones.",
            color=0xFFD700,
            fields=[
                ("📋 Instrucciones", "Este contenido es confidencial. No compartas la información de este canal.", False),
                ("⚠️ Advertencia", "Las filtraciones serán detectadas y rastreadas.", False),
                ("🛡️ Bot", f"**{BOT_NAME}** — Canary Trap Activo", False),
            ]
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

        embed_response = create_embed(
            "🐦 CANARY TRAP CONFIGURADO",
            f"Canary Trap activado en {channel.mention}",
            color=0x00FF00,
            fields=[
                ("📍 Canal", channel.mention, True),
                ("👥 Usuarios", str(len(canary_links)), True),
                ("🔗 Links únicos", "Generados para cada usuario", True),
                ("👑 Configurado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed_response)

        # Log
        await db.add_log(
            guild_id, "canary_setup",
            interaction.user.id,
            details=f"Canary Trap activado en #{channel.name} — {len(canary_links)} usuarios"
        )

    @app_commands.command(name="canaryinfo", description="🐦 Ver estado del Canary Trap")
    async def canary_info(self, interaction: discord.Interaction):
        """Muestra el estado del Canary Trap"""
        if not await self._check_security_role(interaction):
            return

        guild_id = interaction.guild.id
        canary_links = self.canary_links.get(guild_id, {})
        leaked = self.leaked_users.get(guild_id, set())

        if not canary_links:
            embed = create_embed(
                "🐦 Canary Trap",
                "No está configurado. Usa `/canary` para activarlo.",
                color=0x00BFFF
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = create_embed(
            "🐦 ESTADO DEL CANARY TRAP",
            f"Estado actual del Canary Trap en **{interaction.guild.name}**",
            color=0xFFD700,
            fields=[
                ("👥 Usuarios monitoreados", str(len(canary_links)), True),
                ("🚨 Filtraciones detectadas", str(len(leaked)), True),
                ("🔗 Links activos", str(len(canary_links) - len(leaked)), True),
                ("🛡️ Estado", "🟢 ACTIVO" if canary_links else "🔴 INACTIVO", True),
            ]
        )

        if leaked:
            leaked_names = []
            for user_id in list(leaked)[:10]:
                member = interaction.guild.get_member(user_id)
                if member:
                    leaked_names.append(f"• {member.mention}")
                else:
                    leaked_names.append(f"• `{user_id}` (desconocido)")

            embed.add_field(
                name="🚨 Usuarios con filtración",
                value="\n".join(leaked_names),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="canaryleak", description="🚨 Reportar filtración de contenido")
    @app_commands.describe(user="Usuario sospechoso", content="Contenido filtrado")
    async def report_leak(self, interaction: discord.Interaction, user: discord.Member, content: str):
        """Reporta una filtración de contenido"""
        if not await self._check_security_role(interaction):
            return

        guild_id = interaction.guild.id

        # Marcar al usuario como filtrador
        if guild_id not in self.leaked_users:
            self.leaked_users[guild_id] = set()
        self.leaked_users[guild_id].add(user.id)

        # Calcular hash del contenido para rastrear
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Buscar coincidencias en el historial
        matches = []
        for stored_user_id, stored_content, stored_time in self.canary_messages.get(guild_id, []):
            if stored_content and content[:100] in stored_content:
                matches.append((stored_user_id, stored_time))

        embed = create_embed(
            "🚨 FILTRACIÓN REPORTADA",
            f"**{user.mention}** ha sido marcado como filtrador",
            color=0xFF0000,
            fields=[
                ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
                ("📝 Contenido filtrado", content[:500], False),
                ("🔗 Hash", f"`{content_hash}`", True),
                ("📅 Hora", f"<t:{int(time.time())}:F>", True),
                ("🛡️ Bot", f"**{BOT_NAME}** — Canary Trap", False),
            ]
        )

        if matches:
            match_info = []
            for match_user_id, match_time in matches[:5]:
                member = interaction.guild.get_member(match_user_id)
                name = member.mention if member else f"`{match_user_id}`"
                match_info.append(f"• {name} — {match_time}")
            embed.add_field(name="🔍 Coincidencias", value="\n".join(match_info), inline=False)

        await interaction.response.send_message(embed=embed)

        # Log
        await db.add_log(
            guild_id, "canary_leak_reported",
            user.id,
            interaction.user.id,
            details=f"Filtración reportada — Hash: {content_hash}"
        )

    @app_commands.command(name="canaryclear", description="🐦 Limpiar Canary Trap")
    async def canary_clear(self, interaction: discord.Interaction):
        """Limpia el estado del Canary Trap"""
        if not await self._check_security_role(interaction):
            return

        guild_id = interaction.guild.id

        self.canary_links.pop(guild_id, None)
        self.canary_messages.pop(guild_id, None)
        self.leaked_users.pop(guild_id, None)
        self.message_hashes.pop(guild_id, None)

        embed = create_embed(
            "🐦 CANARY TRAP LIMPIADO",
            "El estado del Canary Trap ha sido limpiado.",
            color=0x00FF00,
            fields=[
                ("👑 Limpiado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await db.add_log(
            guild_id, "canary_cleared",
            interaction.user.id,
            details="Canary Trap limpiado"
        )

    # ═══════════════════════════════════════════
    #  MONITOREO
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitorea mensajes para Canary Trap"""
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        now = time.time()

        # Verificar si el canal tiene Canary Trap
        canary_links = self.canary_links.get(guild_id, {})
        if not canary_links:
            return

        # Almacenar mensaje
        self.canary_messages[guild_id].append((user_id, message.content, now))

        # Mantener solo los últimos 1000 mensajes
        if len(self.canary_messages[guild_id]) > 1000:
            self.canary_messages[guild_id] = self.canary_messages[guild_id][-1000:]

        # Verificar si el contenido fue filtrado
        content_hash = hashlib.md5(message.content.encode()).hexdigest()

        if content_hash in self.message_hashes.get(guild_id, set()):
            # Contenido duplicado detectado - posible filtración
            if user_id not in self.leaked_users.get(guild_id, set()):
                if guild_id not in self.leaked_users:
                    self.leaked_users[guild_id] = set()
                self.leaked_users[guild_id].add(user_id)

                # Alerta
                settings = await db.get_guild_settings(guild_id)
                if settings and settings.get('log_channel_id'):
                    channel = message.guild.get_channel(settings['log_channel_id'])
                    if channel:
                        embed = create_embed(
                            "🚨 FILTRACIÓN DETECTADA",
                            f"**{message.author.mention}** posiblemente filtró contenido canary",
                            color=0xFF0000,
                            fields=[
                                ("👤 Usuario", message.author.mention, True),
                                ("📝 Contenido", message.content[:200], False),
                                ("🔗 Hash", f"`{content_hash}`", True),
                                ("🕐 Hora", f"<t:{int(now)}:F>", True),
                            ]
                        )
                        try:
                            await channel.send(embed=embed)
                        except discord.Forbidden:
                            pass

        # Agregar hash
        if guild_id not in self.message_hashes:
            self.message_hashes[guild_id] = set()
        self.message_hashes[guild_id].add(content_hash)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    def _generate_canary_code(self, user_id, guild_id):
        """Genera un código canary único para un usuario"""
        raw = f"{user_id}_{guild_id}_{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

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
    await bot.add_cog(CanaryCog(bot))
