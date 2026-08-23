"""
cogs/moderation.py — Moderación v6
Ban, Kick, Mute, Warn con DMs automáticos
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta

from config import (
    SECURITY_ROLES, WARN_MUTE_THRESHOLD, WARN_KICK_THRESHOLD,
    WARN_BAN_THRESHOLD, COLOR_RED, COLOR_YELLOW, COLOR_GREEN, COLOR_BLUE
)
from utils.embeds import create_embed, user_banned, user_kicked, user_muted, user_warned
from database import db


class Moderation(commands.Cog):
    """Sistema de moderación"""

    def __init__(self, bot):
        self.bot = bot

    # ═══════════════════════════════════════════
    #  WARN
    # ═══════════════════════════════════════════

    @app_commands.command(name="warn", description="Advertir a un usuario")
    @app_commands.describe(user="Usuario", reason="Razón")
    async def warn_cmd(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        if not self._check_role(interaction): return
        if user.bot:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedo advertir a bots.", COLOR_RED), ephemeral=True)

        await db.add_warn(interaction.guild.id, user.id, interaction.user.id, reason)
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)
        warn_ban = (await db.get_settings(interaction.guild.id) or {}).get("warn_ban", WARN_BAN_THRESHOLD)

        await interaction.response.send_message(embed=user_warned(user, reason, warn_count, warn_ban))

        # DM
        await self._dm(user, "⚠️ ADVERTENCIA",
            f"Has recibido una advertencia en **{interaction.guild.name}**",
            COLOR_YELLOW,
            [("📝 Razón", reason, False),
             ("🔢 Warns", f"{warn_count}/{warn_ban}", True),
             ("👮 Moderador", interaction.user.mention, True)])

        await db.add_log(interaction.guild.id, "warn", user.id, interaction.user.id, reason)

        # Auto-acciones
        settings = await db.get_settings(interaction.guild.id) or {}
        if warn_count >= settings.get("warn_ban", WARN_BAN_THRESHOLD):
            await self._auto_action(user, interaction, "ban", warn_count)
        elif warn_count >= settings.get("warn_kick", WARN_KICK_THRESHOLD):
            await self._auto_action(user, interaction, "kick", warn_count)
        elif warn_count >= WARN_MUTE_THRESHOLD:
            await self._auto_action(user, interaction, "mute", warn_count)

    @app_commands.command(name="warns", description="Ver advertencias de un usuario")
    @app_commands.describe(user="Usuario")
    async def warns_cmd(self, interaction: discord.Interaction, user: discord.Member):
        warns = await db.get_warns(interaction.guild.id, user.id)
        if not warns:
            return await interaction.response.send_message(
                embed=create_embed("📋 Warns", f"**{user.mention}** no tiene advertencias.", COLOR_GREEN))

        lines = []
        for i, w in enumerate(warns[:10], 1):
            mod = interaction.guild.get_member(w[3])
            mod_name = mod.mention if mod else f"`{w[3]}`"
            lines.append(f"**{i}.** {w[4]} — {mod_name}")

        await interaction.response.send_message(embed=create_embed(
            f"📋 Warns de {user.name}", f"Total: **{len(warns)}**", COLOR_YELLOW,
            [("📜 Lista", "\n".join(lines), False)]))

    @app_commands.command(name="clearwarns", description="Limpiar advertencias de un usuario")
    @app_commands.describe(user="Usuario")
    async def clearwarns_cmd(self, interaction: discord.Interaction, user: discord.Member):
        if not self._check_role(interaction): return
        await db.clear_warns(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=create_embed("✅ Warns Limpiados",
            f"Advertencias de **{user.mention}** eliminadas.", COLOR_GREEN))

    # ═══════════════════════════════════════════
    #  BAN
    # ═══════════════════════════════════════════

    @app_commands.command(name="ban", description="Banear a un usuario")
    @app_commands.describe(user="Usuario", reason="Razón", delete_messages="Días de mensajes a borrar (0-7)")
    async def ban_cmd(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón", delete_messages: int = 0):
        if not self._check_role(interaction): return
        if user.bot:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedo banear a bots.", COLOR_RED), ephemeral=True)
        if user.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedes banear a alguien con rol igual o superior.", COLOR_RED), ephemeral=True)

        # DM antes del ban
        await self._dm(user, "🔨 BANEADO",
            f"Has sido baneado de **{interaction.guild.name}**",
            COLOR_RED,
            [("📝 Razón", reason, False),
             ("👮 Moderador", interaction.user.mention, True),
             ("📋 ID", f"`{user.id}`", True)])

        await user.ban(reason=f"{interaction.user}: {reason}", delete_message_days=delete_messages)
        await interaction.response.send_message(embed=user_banned(user, reason, interaction.user))
        await db.add_log(interaction.guild.id, "ban", user.id, interaction.user.id, reason)

    @app_commands.command(name="unban", description="Desbanear a un usuario por ID")
    @app_commands.describe(user_id="ID del usuario")
    async def unban_cmd(self, interaction: discord.Interaction, user_id: str):
        if not self._check_role(interaction): return
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "ID inválido.", COLOR_RED), ephemeral=True)
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user)
            await interaction.response.send_message(embed=create_embed("✅ DESBANEADO",
                f"**{user}** ha sido desbaneado", COLOR_GREEN,
                [("👤 Usuario", f"`{user}`\n`{user.id}`", True),
                 ("👮 Moderador", interaction.user.mention, True)]))
            await db.add_log(interaction.guild.id, "unban", uid, interaction.user.id)
        except discord.NotFound:
            await interaction.response.send_message(embed=create_embed("❌ Error", "Usuario no encontrado.", COLOR_RED), ephemeral=True)

    # ═══════════════════════════════════════════
    #  KICK
    # ═══════════════════════════════════════════

    @app_commands.command(name="kick", description="Expulsar a un usuario")
    @app_commands.describe(user="Usuario", reason="Razón")
    async def kick_cmd(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        if not self._check_role(interaction): return
        if user.bot:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedo expulsar a bots.", COLOR_RED), ephemeral=True)
        if user.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedes expulsar a alguien con rol igual o superior.", COLOR_RED), ephemeral=True)

        await self._dm(user, "👢 EXPULSADO",
            f"Has sido expulsado de **{interaction.guild.name}**",
            COLOR_YELLOW,
            [("📝 Razón", reason, False),
             ("👮 Moderador", interaction.user.mention, True),
             ("📋 Puedes volver", "Sí, con nueva invitación", True)])

        await user.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(embed=user_kicked(user, reason, interaction.user))
        await db.add_log(interaction.guild.id, "kick", user.id, interaction.user.id, reason)

    # ═══════════════════════════════════════════
    #  MUTE
    # ═══════════════════════════════════════════

    @app_commands.command(name="mute", description="Silenciar a un usuario")
    @app_commands.describe(user="Usuario", duration="Duración en minutos", reason="Razón")
    async def mute_cmd(self, interaction: discord.Interaction, user: discord.Member, duration: int = 5, reason: str = "Sin razón"):
        if not self._check_role(interaction): return
        if user.bot:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "No puedo silenciar a bots.", COLOR_RED), ephemeral=True)

        until = discord.utils.utcnow() + timedelta(minutes=duration)
        await user.timeout(until, reason=f"{interaction.user}: {reason}")

        await self._dm(user, "🔇 SILENCIADO",
            f"Has sido silenciado en **{interaction.guild.name}**",
            COLOR_BLUE,
            [("📝 Razón", reason, False),
             ("⏱️ Duración", f"{duration} minutos", True),
             ("🕐 Se desilencia", f"<t:{int(until.timestamp())}:R>", True),
             ("👮 Moderador", interaction.user.mention, True)])

        await interaction.response.send_message(embed=user_muted(user, duration, reason))
        await db.add_log(interaction.guild.id, "mute", user.id, interaction.user.id, f"{reason} ({duration}min)")

    @app_commands.command(name="unmute", description="Quitar silencio a un usuario")
    @app_commands.describe(user="Usuario")
    async def unmute_cmd(self, interaction: discord.Interaction, user: discord.Member):
        if not self._check_role(interaction): return
        await user.timeout(None, reason=f"Desilenciado por {interaction.user}")

        await self._dm(user, "🔊 PUEDES HABLAR",
            f"Tu silencio en **{interaction.guild.name}** ha sido removido.", COLOR_GREEN)

        await interaction.response.send_message(embed=create_embed("🔊 SILENCIO REMOVIDO",
            f"**{user.mention}** ya puede hablar de nuevo", COLOR_GREEN,
            [("👤 Usuario", user.mention, True), ("👮 Moderador", interaction.user.mention, True)]))
        await db.add_log(interaction.guild.id, "unmute", user.id, interaction.user.id)

    # ═══════════════════════════════════════════
    #  LOG CHANNEL
    # ═══════════════════════════════════════════

    @app_commands.command(name="setlog", description="Establecer canal de logs de seguridad")
    @app_commands.describe(channel="Canal para logs")
    async def setlog_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not self._check_role(interaction): return
        await db.update_settings(interaction.guild.id, log_channel_id=channel.id)
        await interaction.response.send_message(embed=create_embed("✅ Canal de Logs",
            f"Logs configurados en {channel.mention}", COLOR_GREEN,
            [("📍 Canal", channel.mention, True)]))

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    def _check_role(self, interaction):
        if any(r.name in SECURITY_ROLES for r in interaction.user.roles):
            return True
        import asyncio
        asyncio.get_event_loop().create_task(
            interaction.response.send_message(
                embed=create_embed("❌ Sin permisos", "Necesitas un rol de moderador.", COLOR_RED),
                ephemeral=True))
        return False

    async def _dm(self, user, title, description, color, fields=None):
        try:
            await user.send(embed=create_embed(title, description, color, fields))
        except discord.Forbidden:
            pass

    async def _auto_action(self, user, interaction, action, warn_count):
        if action == "ban":
            await self._dm(user, "🔨 BAN AUTOMÁTICO",
                f"Has sido baneado automáticamente de **{interaction.guild.name}** por exceso de advertencias ({warn_count}).",
                COLOR_RED, [("🔢 Warns", str(warn_count), True)])
            try:
                await user.ban(reason=f"Auto-ban: {warn_count} warns")
            except discord.Forbidden:
                pass
        elif action == "kick":
            await self._dm(user, "👢 KICK AUTOMÁTICO",
                f"Has sido expulsado automáticamente de **{interaction.guild.name}** por exceso de advertencias ({warn_count}).",
                COLOR_YELLOW, [("🔢 Warns", str(warn_count), True)])
            try:
                await user.kick(reason=f"Auto-kick: {warn_count} warns")
            except discord.Forbidden:
                pass
        elif action == "mute":
            until = discord.utils.utcnow() + timedelta(minutes=10)
            try:
                await user.timeout(until, reason=f"Auto-mute: {warn_count} warns")
                await self._dm(user, "🔇 MUTE AUTOMÁTICO",
                    f"Has sido silenciado automáticamente en **{interaction.guild.name}**.",
                    COLOR_BLUE, [("⏱️ Duración", "10 minutos", True),
                                 ("🔢 Warns", str(warn_count), True)])
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(Moderation(bot))
