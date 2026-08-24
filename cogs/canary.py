"""
cogs/canary.py — Canary Trap Anti-Infiltrados
Detecta filtraciones de contenido con links unicos por usuario
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import hashlib
import time

from config import (
    SECURITY_ROLES, COLOR_RED, COLOR_GREEN, COLOR_YELLOW,
    COLOR_BLUE, COLOR_ORANGE, BOT_NAME
)
from utils.embeds import create_embed
from database import db


class Canary(commands.Cog):
    """Sistema Canary Trap para detectar infiltrados"""

    def __init__(self, bot):
        self.bot = bot
        # Canal -> {canary_links: {user_id: unique_link}}
        self.canary_links = {}
        # Canal -> contenido original (con canary insertado)
        self.canary_content = {}
        # Leak reports
        self.leak_reports = {}

    # ==========================================
    #  COMANDOS
    # ==========================================

    @app_commands.command(name="canary", description="Configurar Canary Trap en un canal")
    @app_commands.describe(channel="Canal a proteger", content="Texto con canary (usa {canary} para insertar)")
    async def canary_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, content: str):
        if not self._check_role(interaction):
            return

        # Insertar canary unico para cada usuario
        guild_id = interaction.guild.id
        channel_id = channel.id

        if channel_id not in self.canary_links:
            self.canary_links[channel_id] = {}

        # Generar link unico por miembro
        count = 0
        for member in interaction.guild.members:
            if not member.bot:
                unique = hashlib.md5((str(member.id) + str(channel_id)).encode()).hexdigest()[:12]
                self.canary_links[channel_id][member.id] = unique
                count += 1

        self.canary_content[channel_id] = content

        await interaction.response.send_message(embed=create_embed(
            "🐦 CANARY TRAP ACTIVADO",
            "Canal **" + channel.mention + "** protegido con Canary Trap",
            COLOR_GREEN,
            [("📍 Canal", channel.mention, True),
             ("👥 Usuarios monitoreados", str(count), True),
             ("📝 Contenido", content[:200], False),
             ("💡 Como funciona", "Cada usuario recibe un link unico. Si el contenido se filtra, el link revela quien fue.", False)]))

        # Log
        await db.add_log(guild_id, "canary_setup", interaction.user.id,
                        details="Canal: " + channel.name + " | Usuarios: " + str(count))

    @app_commands.command(name="canaryinfo", description="Ver estado del Canary Trap")
    async def canaryinfo_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return

        guild = interaction.guild
        protected_channels = []

        for channel_id, links in self.canary_links.items():
            ch = guild.get_channel(channel_id)
            if ch:
                protected_channels.append(ch.mention + " (" + str(len(links)) + " usuarios)")

        if not protected_channels:
            return await interaction.response.send_message(embed=create_embed(
                "🐦 CANARY TRAP",
                "No hay canales protegidos. Usa `/canary #canal` para configurar.",
                COLOR_YELLOW))

        await interaction.response.send_message(embed=create_embed(
            "🐦 CANARY TRAP - ESTADO",
            "Canales protegidos con Canary Trap",
            COLOR_BLUE,
            [("📍 Canales", "\n".join(protected_channels), False),
             ("📊 Total", str(len(protected_channels)) + " canales", True)]))

    @app_commands.command(name="canaryleak", description="Reportar una filtracion")
    @app_commands.describe(user="Usuario sospechoso de filtrar")
    async def canaryleak_cmd(self, interaction: discord.Interaction, user: discord.Member):
        if not self._check_role(interaction):
            return

        guild = interaction.guild

        # Buscar el canary del usuario
        for channel_id, links in self.canary_links.items():
            if user.id in links:
                canary = links[user.id]
                ch = guild.get_channel(channel_id)
                ch_name = ch.mention if ch else "Canal #" + str(channel_id)

                await interaction.response.send_message(embed=create_embed(
                    "🚨 FILTRACION DETECTADA",
                    "El canary de **" + user.name + "** fue encontrado",
                    COLOR_RED,
                    [("👤 Usuario", user.mention + "\n`" + str(user.id) + "`", True),
                     ("📍 Canal", ch_name, True),
                     ("🐦 Canary", "`" + canary + "`", True),
                     ("⚡ Accion", "Este usuario filtro contenido de " + ch_name, False),
                     ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)]))

                # Log
                await db.add_log(guild.id, "canary_leak", user.id, interaction.user.id,
                                details="Canary: " + canary + " | Canal: " + str(channel_id))
                return

        await interaction.response.send_message(embed=create_embed(
            "❌ Sin canary",
            "No se encontro canary para **" + user.name + "**",
            COLOR_YELLOW))

    @app_commands.command(name="canaryclear", description="Limpiar estado de Canary Trap")
    async def canaryclear_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return

        self.canary_links.clear()
        self.canary_content.clear()
        self.leak_reports.clear()

        await interaction.response.send_message(embed=create_embed(
            "🧹 CANARY TRAP LIMPIADO",
            "Todo el estado de Canary Trap ha sido eliminado",
            COLOR_GREEN))

    # ==========================================
    #  UTILIDADES
    # ==========================================

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
    await bot.add_cog(Canary(bot))
