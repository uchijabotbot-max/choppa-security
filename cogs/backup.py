"""
cogs/backup.py - Backup Automatico del Servidor
Guarda canales, roles y configuracion periodicamente
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime

from config import (
    BACKUP_ENABLED, BACKUP_INTERVAL_HOURS, SECURITY_ROLES,
    COLOR_RED, COLOR_GREEN, COLOR_BLUE, BOT_NAME, BOT_FOOTER, OWNER_ID
)
from utils.embeds import create_embed
from database import db


class Backup(commands.Cog):
    """Sistema de backup automatico del servidor"""

    def __init__(self, bot):
        self.bot = bot
        self.backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        if BACKUP_ENABLED:
            self.auto_backup.start()

    def cog_unload(self):
        if BACKUP_ENABLED:
            self.auto_backup.cancel()

    @tasks.loop(hours=BACKUP_INTERVAL_HOURS)
    async def auto_backup(self):
        """Backup automatico cada N horas"""
        for guild in self.bot.guilds:
            try:
                await self._do_backup(guild)
            except Exception as e:
                print(f"Error en backup de {guild.name}: {e}")

    @auto_backup.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

    # ==========================================
    #  COMANDOS
    # ==========================================

    @app_commands.command(name="backup", description="Crear backup del servidor ahora")
    async def backup_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return
        await interaction.response.defer()
        data = await self._do_backup(interaction.guild)
        await interaction.followup.send(embed=create_embed("✅ BACKUP CREADO",
            "Backup del servidor **" + interaction.guild.name + "** creado exitosamente",
            COLOR_GREEN,
            [("📁 Archivo", data["filename"], True),
             ("📅 Hora", data["timestamp"], True),
             ("📝 Canales", str(data["channel_count"]), True),
             ("🎭 Roles", str(data["role_count"]), True)]))

    @app_commands.command(name="backups", description="Ver todos los backups del servidor")
    async def backups_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return
        files = self._get_backups(interaction.guild.id)
        if not files:
            return await interaction.response.send_message(embed=create_embed("📁 Backups",
                "No hay backups. Usa `/backup` para crear uno.", COLOR_BLUE))

        lines = []
        for f in files[-10:]:
            lines.append("- " + f)

        await interaction.response.send_message(embed=create_embed("📁 Backups del Servidor",
            "\n".join(lines), COLOR_BLUE,
            [("📊 Total", str(len(files)), True)]))

    # ==========================================
    #  BACKUP ENGINE
    # ==========================================

    async def _do_backup(self, guild):
        """Crea un backup completo del servidor"""
        data = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "owner_id": guild.owner_id,
            "member_count": guild.member_count,
            "channels": [],
            "roles": [],
            "emoji_count": len(guild.emojis),
            "boost_level": guild.premium_tier,
            "verification_level": str(guild.verification_level),
        }

        # Canales
        for ch in guild.channels:
            ch_data = {
                "id": ch.id,
                "name": ch.name,
                "type": str(ch.type),
                "category": ch.category.name if ch.category else None,
            }
            data["channels"].append(ch_data)

        # Roles
        for role in guild.roles:
            if role.name == "@everyone":
                continue
            perms = []
            for perm, value in role.permissions:
                if value:
                    perms.append(perm)
            role_data = {
                "id": role.id,
                "name": role.name,
                "color": role.color.value,
                "position": role.position,
                "permissions": perms,
                "mentionable": role.mentionable,
                "hoist": role.hoist,
            }
            data["roles"].append(role_data)

        data["channel_count"] = len(data["channels"])
        data["role_count"] = len(data["roles"])

        # Guardar archivo
        filename = "backup_" + str(guild.id) + "_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json"
        filepath = os.path.join(self.backup_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        data["filename"] = filename

        # Log
        await db.add_log(guild.id, "backup_created", details="Archivo: " + filename)

        # Alerta en logs
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    embed = create_embed("💾 BACKUP CREADO",
                        "Backup automatico del servidor",
                        COLOR_BLUE,
                        [("📁 Archivo", filename, False),
                         ("📝 Canales", str(data["channel_count"]), True),
                         ("🎭 Roles", str(data["role_count"]), True),
                         ("👥 Miembros", str(data["member_count"]), True)])
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass

        return data

    def _get_backups(self, guild_id):
        """Obtiene lista de backups de un servidor"""
        prefix = "backup_" + str(guild_id) + "_"
        files = []
        for f in sorted(os.listdir(self.backup_dir)):
            if f.startswith(prefix) and f.endswith(".json"):
                files.append(f)
        return files

    def _check_role(self, interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.id == interaction.guild.owner_id or str(interaction.user.id) == str(OWNER_ID):
            return True
        import asyncio
        asyncio.get_event_loop().create_task(
            interaction.response.send_message(
                embed=create_embed("❌ Sin permisos", "Solo el **dueño del servidor** tiene acceso a los comandos.", COLOR_RED),
                ephemeral=True))
        return False


async def setup(bot):
    await bot.add_cog(Backup(bot))
