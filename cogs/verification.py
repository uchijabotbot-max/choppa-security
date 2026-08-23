# ─────────────────────────────────────────────
#  cogs/verification.py — Sistema de Verificación
#  Captcha, verificación por DM, roles automáticos
# ─────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
import random
import string
import asyncio

from config import (
    VERIFICATION_CHANNEL_NAME, VERIFIED_ROLE_NAME,
    VERIFICATION_TIMEOUT, SECURITY_ROLES
)
from utils.embeds import create_embed, welcome_embed
from database import db


class VerificationCog(commands.Cog):
    """Sistema de verificación avanzado"""

    def __init__(self, bot):
        self.bot = bot
        self.pending_codes = {}  # user_id -> code

    # ═══════════════════════════════════════════
    #  EVENTO: NUEVO MIEMBRO
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Envía instrucciones de verificación al nuevo miembro"""
        if member.bot:
            return

        settings = await db.get_guild_settings(member.guild.id)
        if not settings or not settings.get('verification', False):
            return

        # Buscar canal de verificación
        verify_channel_id = settings.get('verification_channel_id')
        if not verify_channel_id:
            return

        channel = member.guild.get_channel(verify_channel_id)
        if not channel:
            return

        # Enviar DM con código de verificación
        code = self._generate_code()
        self.pending_codes[member.id] = code

        try:
            dm_embed = create_embed(
                "🔐 VERIFICACIÓN",
                f"Para acceder a **{member.guild.name}**, necesitas verificar tu cuenta.",
                color=0x00BFFF,
                fields=[
                    ("📝 Tu código", f"```{code}```", False),
                    ("⏱️ Tiempo", f"Tienes {VERIFICATION_TIMEOUT // 60} minutos", True),
                    ("📍 Canal", channel.mention, True),
                ]
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Embed en el canal de verificación
        embed = create_embed(
            "🔐 Verificación requerida",
            f"**{member.mention}**, revisa tu DM para obtener tu código de verificación.",
            color=0x00BFFF,
            fields=[
                ("📝 Instrucciones", "Escribe tu código en este canal para verificar tu cuenta.", False),
                ("⏱️ Tiempo", f"{VERIFICATION_TIMEOUT // 60} minutos para completar la verificación", True),
            ]
        )
        await channel.send(embed=embed)

        # Timer para expirar la verificación
        await asyncio.sleep(VERIFICATION_TIMEOUT)
        if member.id in self.pending_codes:
            del self.pending_codes[member.id]
            try:
                await member.send(embed=create_embed(
                    "❌ Verificación expirada",
                    "Tu código de verificación ha expirado. Únete de nuevo para obtener un nuevo código.",
                    color=0xFF0000
                ))
            except discord.Forbidden:
                pass

    # ═══════════════════════════════════════════
    #  COMANDOS
    # ═══════════════════════════════════════════

    @app_commands.command(name="verifysetup", description="Configurar el sistema de verificación")
    @app_commands.describe(channel="Canal de verificación", role="Rol para miembros verificados")
    async def verify_setup(self, interaction: discord.Interaction,
                           channel: discord.TextChannel = None,
                           role: discord.Role = None):
        """Configura el sistema de verificación"""
        if not await self._check_mod_role(interaction):
            return

        updates = {'verification': 1}

        if channel:
            updates['verification_channel_id'] = channel.id

        if role:
            updates['verified_role_id'] = role.id

        await db.update_guild_settings(interaction.guild.id, **updates)

        embed = create_embed(
            "✅ Sistema de verificación configurado",
            "El sistema de verificación ha sido activado.",
            color=0x00FF00,
            fields=[
                ("📍 Canal", channel.mention if channel else "No cambiado", True),
                ("🎭 Rol", role.mention if role else "No cambiado", True),
                ("👑 Configurado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="verify", description="Verificar tu cuenta manualmente")
    @app_commands.describe(code="Tu código de verificación")
    async def verify_manual(self, interaction: discord.Interaction, code: str):
        """Verifica tu cuenta con un código"""
        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings or not settings.get('verification', False):
            embed = create_embed("❌ Error", "La verificación no está activa en este servidor.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Verificar el código
        expected_code = self.pending_codes.get(interaction.user.id)
        if expected_code and code.upper() == expected_code.upper():
            # Verificar al usuario
            del self.pending_codes[interaction.user.id]

            # Dar rol verificado
            verified_role_id = settings.get('verified_role_id')
            if verified_role_id:
                role = interaction.guild.get_role(verified_role_id)
                if role:
                    try:
                        await interaction.user.add_roles(role)
                    except discord.Forbidden:
                        pass

            # Embed de bienvenida
            embed = welcome_embed(interaction.user)
            await interaction.response.send_message(embed=embed)

            # Log
            await db.add_log(interaction.guild.id, "member_verified", interaction.user.id)

            # DM de confirmación
            try:
                dm_embed = create_embed(
                    "✅ VERIFICADO",
                    f"Tu cuenta ha sido verificada en **{interaction.guild.name}**.",
                    color=0x00FF00,
                    fields=[
                        ("🎭 Rol", role.mention if role else "N/A", True),
                        ("🎉 Bienvenido", "¡Disfruta tu estancia!", True),
                    ]
                )
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        else:
            embed = create_embed(
                "❌ Código incorrecto",
                "El código ingresado es incorrecto. Revisa tu DM y vuelve a intentar.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="disableverify", description="Desactivar el sistema de verificación")
    async def disable_verify(self, interaction: discord.Interaction):
        """Desactiva la verificación"""
        if not await self._check_mod_role(interaction):
            return

        await db.update_guild_settings(interaction.guild.id, verification=0)

        embed = create_embed(
            "✅ Verificación desactivada",
            "El sistema de verificación ha sido desactivado.",
            color=0x00FF00,
            fields=[
                ("👑 Desactivado por", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="resendcode", description="Reenviar código de verificación a un usuario")
    @app_commands.describe(user="Usuario a reenviar código")
    async def resend_code(self, interaction: discord.Interaction, user: discord.Member):
        """Reenvía el código de verificación a un usuario"""
        if not await self._check_mod_role(interaction):
            return

        code = self._generate_code()
        self.pending_codes[user.id] = code

        try:
            dm_embed = create_embed(
                "🔐 NUEVO CÓDIGO DE VERIFICACIÓN",
                f"Tu nuevo código de verificación para **{interaction.guild.name}**:",
                color=0x00BFFF,
                fields=[
                    ("📝 Tu código", f"```{code}```", False),
                    ("⏱️ Tiempo", f"{VERIFICATION_TIMEOUT // 60} minutos", True),
                ]
            )
            await user.send(embed=dm_embed)

            embed = create_embed(
                "✅ Código reenviado",
                f"Se envió un nuevo código de verificación a **{user.mention}**",
                color=0x00FF00
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            embed = create_embed(
                "❌ Error",
                f"No pude enviar DM a **{user.mention}**. Tiene los DMs bloqueados.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    def _generate_code(self):
        """Genera un código de verificación aleatorio"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

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
    await bot.add_cog(VerificationCog(bot))
