# ─────────────────────────────────────────────
#  cogs/moderation.py — Sistema de Moderación
#  Ban, Kick, Mute, Warn con DMs automáticos
# ─────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta

from config import (
    WARN_KICK_THRESHOLD, WARN_BAN_THRESHOLD,
    WARN_MUTE_THRESHOLD, SECURITY_ROLES
)
from utils.embeds import (
    user_warned, user_kicked, user_banned, user_muted,
    create_embed
)
from database import db


class ModerationCog(commands.Cog):
    """Sistema de moderación completo"""

    def __init__(self, bot):
        self.bot = bot

    # ═══════════════════════════════════════════
    #  WARNS
    # ═══════════════════════════════════════════

    @app_commands.command(name="warn", description="Advertir a un usuario")
    @app_commands.describe(user="Usuario a advertir", reason="Razón de la advertencia")
    async def warn_user(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        """Advierte a un usuario y le envía DM con la info"""
        if not await self._check_mod_role(interaction):
            return

        # No warns a bots
        if user.bot:
            embed = create_embed("❌ Error", "No puedo advertir a bots.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Warn al usuario
        await db.add_warn(interaction.guild.id, user.id, interaction.user.id, reason)
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)

        # Embed de respuesta
        embed = user_warned(user, reason, warn_count)
        await interaction.response.send_message(embed=embed)

        # DM al usuario con toda la información
        try:
            dm_embed = create_embed(
                "⚠️ ADVERTENCIA",
                f"Has recibido una advertencia en **{interaction.guild.name}**",
                color=0xFFFF00,
                fields=[
                    ("📝 Razón", reason, False),
                    ("🔢 Total de advertencias", f"{warn_count}/5", True),
                    ("⚠️ Siguiente acción", self._get_next_action(warn_count), True),
                    ("👮 Moderador", interaction.user.mention, True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Log de seguridad
        await self._log_moderation(interaction, "warn", user, reason)

        # Auto-acciones basadas en warns
        settings = await db.get_guild_settings(interaction.guild.id)
        kick_threshold = settings.get('warn_kick_threshold', WARN_KICK_THRESHOLD) if settings else WARN_KICK_THRESHOLD
        ban_threshold = settings.get('warn_ban_threshold', WARN_BAN_THRESHOLD) if settings else WARN_BAN_THRESHOLD

        if warn_count >= ban_threshold:
            await self._auto_ban(user, interaction, warn_count)
        elif warn_count >= kick_threshold:
            await self._auto_kick(user, interaction, warn_count)

    @app_commands.command(name="warns", description="Ver advertencias de un usuario")
    @app_commands.describe(user="Usuario a consultar")
    async def check_warns(self, interaction: discord.Interaction, user: discord.Member):
        """Muestra todas las advertencias de un usuario"""
        warns = await db.get_warns(interaction.guild.id, user.id)

        if not warns:
            embed = create_embed(
                "📋 Advertencias",
                f"**{user.mention}** no tiene advertencias.",
                color=0x00FF00
            )
            await interaction.response.send_message(embed=embed)
            return

        warn_list = []
        for i, w in enumerate(warns[:10], 1):
            moderator = interaction.guild.get_member(w[3])
            mod_name = moderator.mention if moderator else f"`{w[3]}`"
            warn_list.append(f"**{i}.** {w[4]} — {mod_name} (<t:{int(w[5].timestamp()) if hasattr(w[5], 'timestamp') else 0}:R>)")

        embed = create_embed(
            f"📋 Advertencias de {user.name}",
            f"Total: **{len(warns)}** advertencias",
            color=0xFFFF00,
            fields=[
                ("📜 Lista", "\n".join(warn_list), False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Limpiar advertencias de un usuario")
    @app_commands.describe(user="Usuario a limpiar")
    async def clear_warns_cmd(self, interaction: discord.Interaction, user: discord.Member):
        """Limpia todas las advertencias de un usuario"""
        if not await self._check_mod_role(interaction):
            return

        await db.clear_warns(interaction.guild.id, user.id)

        embed = create_embed(
            "✅ Advertencias limpiadas",
            f"Todas las advertencias de **{user.mention}** han sido eliminadas.",
            color=0x00FF00,
            fields=[
                ("👮 Moderador", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  BAN
    # ═══════════════════════════════════════════

    @app_commands.command(name="ban", description="Banear a un usuario permanentemente")
    @app_commands.describe(user="Usuario a banear", reason="Razón del baneo", delete_messages="Días de mensajes a borrar (0-7)")
    async def ban_user(self, interaction: discord.Interaction, user: discord.Member,
                       reason: str = "Sin razón", delete_messages: int = 0):
        """Banea a un usuario y le envía DM con la info"""
        if not await self._check_mod_role(interaction):
            return

        if user.bot:
            embed = create_embed("❌ Error", "No puedo banear a bots.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if user.top_role >= interaction.user.top_role:
            embed = create_embed("❌ Error", "No puedo banear a alguien con un rol igual o superior al tuyo.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # DM al usuario ANTES de banear
        try:
            dm_embed = create_embed(
                "🔨 BANEADO",
                f"Has sido baneado de **{interaction.guild.name}**",
                color=0xFF0000,
                fields=[
                    ("📝 Razón", reason, False),
                    ("👮 Moderador", interaction.user.mention, True),
                    ("⏱️ Tipo", "Permanente", True),
                    ("📋 ID de usuario", f"`{user.id}`", True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Banear
        await user.ban(reason=f"{interaction.user}: {reason}", delete_message_days=delete_messages)

        embed = user_banned(user, reason, interaction.user)
        await interaction.response.send_message(embed=embed)

        await self._log_moderation(interaction, "ban", user, reason)

    @app_commands.command(name="unban", description="Desbanear a un usuario")
    @app_commands.describe(user_id="ID del usuario a desbanear")
    async def unban_user(self, interaction: discord.Interaction, user_id: str):
        """Desbanea a un usuario por su ID"""
        if not await self._check_mod_role(interaction):
            return

        try:
            uid = int(user_id)
        except ValueError:
            embed = create_embed("❌ Error", "ID inválido.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user)

            embed = create_embed(
                "✅ USUARIO DESBANEADO",
                f"**{user}** ha sido desbaneado",
                color=0x00FF00,
                fields=[
                    ("👤 Usuario", f"`{user}`\n`{user.id}`", True),
                    ("👮 Moderador", interaction.user.mention, True),
                ]
            )
            await interaction.response.send_message(embed=embed)

            await self._log_moderation(interaction, "unban", user, "Desbaneado")
        except discord.NotFound:
            embed = create_embed("❌ Error", "Usuario no encontrado en la lista de baneos.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ═══════════════════════════════════════════
    #  KICK
    # ═══════════════════════════════════════════

    @app_commands.command(name="kick", description="Expulsar a un usuario")
    @app_commands.describe(user="Usuario a expulsar", reason="Razón de la expulsión")
    async def kick_user(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        """Expulsa a un usuario y le envía DM con la info"""
        if not await self._check_mod_role(interaction):
            return

        if user.bot:
            embed = create_embed("❌ Error", "No puedo expulsar a bots.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if user.top_role >= interaction.user.top_role:
            embed = create_embed("❌ Error", "No puedo expulsar a alguien con un rol igual o superior al tuyo.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # DM al usuario ANTES de expulsar
        try:
            dm_embed = create_embed(
                "👢 EXPULSADO",
                f"Has sido expulsado de **{interaction.guild.name}**",
                color=0xFFFF00,
                fields=[
                    ("📝 Razón", reason, False),
                    ("👮 Moderador", interaction.user.mention, True),
                    ("📋 Puedes volver a unirte", "Sí, con una nueva invitación", True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Expulsar
        await user.kick(reason=f"{interaction.user}: {reason}")

        embed = user_kicked(user, reason, interaction.user)
        await interaction.response.send_message(embed=embed)

        await self._log_moderation(interaction, "kick", user, reason)

    # ═══════════════════════════════════════════
    #  MUTE / TIMEOUT
    # ═══════════════════════════════════════════

    @app_commands.command(name="mute", description="Silenciar a un usuario")
    @app_commands.describe(user="Usuario a silenciar", duration="Duración en minutos", reason="Razón")
    async def mute_user(self, interaction: discord.Interaction, user: discord.Member,
                        duration: int = 5, reason: str = "Sin razón"):
        """Silencia a un usuario temporalmente"""
        if not await self._check_mod_role(interaction):
            return

        if user.bot:
            embed = create_embed("❌ Error", "No puedo silenciar a bots.", color=0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Timeout
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        await user.timeout(timeout_until, reason=f"{interaction.user}: {reason}")

        # DM al usuario
        try:
            dm_embed = create_embed(
                "🔇 SILENCIADO",
                f"Has sido silenciado en **{interaction.guild.name}**",
                color=0x00BFFF,
                fields=[
                    ("📝 Razón", reason, False),
                    ("⏱️ Duración", f"{duration} minutos", True),
                    ("🕐 Se desilencia", f"<t:{int(timeout_until.timestamp())}:R>", True),
                    ("👮 Moderador", interaction.user.mention, True),
                ]
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        embed = user_muted(user, duration * 60, reason)
        await interaction.response.send_message(embed=embed)

        await self._log_moderation(interaction, "mute", user, f"{reason} ({duration} min)")

    @app_commands.command(name="unmute", description="Quitar silencio a un usuario")
    @app_commands.describe(user="Usuario a desilenciar")
    async def unmute_user(self, interaction: discord.Interaction, user: discord.Member):
        """Quita el silencio a un usuario"""
        if not await self._check_mod_role(interaction):
            return

        await user.timeout(None, reason=f"Desilenciado por {interaction.user}")

        embed = create_embed(
            "🔊 SILENCIO REMOVIDO",
            f"**{user.mention}** ya puede hablar de nuevo",
            color=0x00FF00,
            fields=[
                ("👤 Usuario", user.mention, True),
                ("👮 Moderador", interaction.user.mention, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        # DM al usuario
        try:
            dm_embed = create_embed(
                "🔊 PUEDES HABLAR DE NUEVO",
                f"Tu silencio en **{interaction.guild.name}** ha sido removido.",
                color=0x00FF00
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await self._log_moderation(interaction, "unmute", user, "Silencio removido")

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    def _get_next_action(self, warn_count):
        """Retorna la próxima acción automática"""
        settings = None  # Se obtiene en tiempo real
        if warn_count >= WARN_BAN_THRESHOLD:
            return f"🔨 BAN automático ({warn_count}/{WARN_BAN_THRESHOLD})"
        elif warn_count >= WARN_KICK_THRESHOLD:
            return f"👢 KICK automático ({warn_count}/{WARN_KICK_THRESHOLD})"
        elif warn_count >= WARN_MUTE_THRESHOLD:
            return f"🔇 MUTE automático ({warn_count}/{WARN_MUTE_THRESHOLD})"
        return f"⚠️ {warn_count} advertencias"

    async def _auto_ban(self, user, interaction, warn_count):
        """Ban automático por exceso de warns"""
        try:
            await user.send(embed=create_embed(
                "🔨 BAN AUTOMÁTICO",
                f"Has sido baneado automáticamente de **{interaction.guild.name}** por exceso de advertencias ({warn_count}).",
                color=0xFF0000,
                fields=[
                    ("🔢 Total warns", str(warn_count), True),
                    ("⚠️ Límite", str(WARN_BAN_THRESHOLD), True),
                ]
            ))
        except discord.Forbidden:
            pass

        await user.ban(reason=f"Auto-ban: {warn_count} advertencias")

    async def _auto_kick(self, user, interaction, warn_count):
        """Kick automático por exceso de warns"""
        try:
            await user.send(embed=create_embed(
                "👢 KICK AUTOMÁTICO",
                f"Has sido expulsado automáticamente de **{interaction.guild.name}** por exceso de advertencias ({warn_count}).",
                color=0xFFFF00,
                fields=[
                    ("🔢 Total warns", str(warn_count), True),
                    ("⚠️ Límite", str(WARN_KICK_THRESHOLD), True),
                ]
            ))
        except discord.Forbidden:
            pass

        await user.kick(reason=f"Auto-kick: {warn_count} advertencias")

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

    async def _log_moderation(self, interaction, action, user, reason):
        """Registra una acción de moderación"""
        await db.add_log(
            interaction.guild.id,
            f"mod_{action}",
            user.id,
            interaction.user.id,
            reason
        )

        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings or not settings.get('logs_enabled', True):
            return

        log_channel_id = settings.get('log_channel_id')
        if not log_channel_id:
            return

        channel = interaction.guild.get_channel(log_channel_id)
        if not channel:
            return

        from utils.embeds import create_embed
        action_emojis = {
            "warn": "⚠️",
            "ban": "🔨",
            "unban": "✅",
            "kick": "👢",
            "mute": "🔇",
            "unmute": "🔊",
        }

        emoji = action_emojis.get(action, "📋")
        embed = create_embed(
            f"{emoji} MODERACIÓN: {action.upper()}",
            f"**{user.mention}** fue afectado por {interaction.user.mention}",
            color=0xFF0000 if action in ['ban', 'kick'] else 0xFFFF00,
            fields=[
                ("👤 Usuario", f"{user.mention}\n`{user.id}`", True),
                ("👮 Moderador", interaction.user.mention, True),
                ("📝 Razón", reason, True),
            ]
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
