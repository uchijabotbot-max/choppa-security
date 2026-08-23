# ─────────────────────────────────────────────
#  cogs/backup.py — Sistema de Backup Anti-Raid
#  Backup automático del servidor para restaurar después de un raid
# ─────────────────────────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import time
from datetime import datetime

from config import BOT_NAME, SECURITY_ROLES
from utils.embeds import create_embed
from database import db


BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups")


class BackupCog(commands.Cog):
    """Sistema de backup y restauración del servidor"""

    def __init__(self, bot):
        self.bot = bot
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self.auto_backup.start()

    def cog_unload(self):
        self.auto_backup.cancel()

    # ═══════════════════════════════════════════
    #  BACKUP AUTOMÁTICO
    # ═══════════════════════════════════════════

    @tasks.loop(hours=6)
    async def auto_backup(self):
        """Backup automático cada 6 horas"""
        for guild in self.bot.guilds:
            try:
                await self._create_backup(guild, automatic=True)
            except Exception as e:
                print(f"Error en backup automático para {guild.name}: {e}")

    @auto_backup.before_loop
    async def before_auto_backup(self):
        await self.bot.wait_until_ready()

    # ═══════════════════════════════════════════
    #  COMANDOS
    # ═══════════════════════════════════════════

    @app_commands.command(name="backup", description="💾 Crear backup del servidor")
    async def backup_cmd(self, interaction: discord.Interaction):
        """Crea un backup completo del servidor"""
        if not await self._check_security_role(interaction):
            return

        await interaction.response.defer()

        backup_data = await self._create_backup(interaction.guild, automatic=False)

        embed = create_embed(
            "💾 BACKUP CREADO",
            f"Backup completo de **{interaction.guild.name}** creado exitosamente",
            color=0x00FF00,
            fields=[
                ("📊 Canales", str(len(backup_data['channels'])), True),
                ("🎭 Roles", str(len(backup_data['roles'])), True),
                ("📋 Reglas", str(len(backup_data.get('rules', []))), True),
                ("⏰ Hora", f"<t:{int(time.time())}:F>", True),
                ("💾 Tamaño", f"{len(json.dumps(backup_data)) / 1024:.1f} KB", True),
            ]
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="restore", description="🔄 Restaurar desde backup")
    @app_commands.describe(backup_id="ID del backup a restaurar")
    async def restore_cmd(self, interaction: discord.Interaction, backup_id: str = None):
        """Restaura el servidor desde un backup"""
        if not await self._check_security_role(interaction):
            return

        await interaction.response.defer()

        # Listar backups disponibles
        backups = self._list_backups(interaction.guild.id)

        if not backups:
            embed = create_embed(
                "❌ Sin backups",
                "No hay backups disponibles para este servidor.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
            return

        if backup_id is None:
            # Mostrar lista de backups
            backup_list = []
            for b in backups[:10]:
                backup_list.append(
                    f"**{b['id']}** — {b['timestamp']}\n"
                    f"  📊 {b['channels']} canales | 🎭 {b['roles']} roles"
                )

            embed = create_embed(
                "💾 BACKUPS DISPONIBLES",
                "Selecciona un backup para restaurar",
                color=0x00BFFF,
                fields=[
                    ("📋 Lista", "\n\n".join(backup_list), False),
                    ("📝 Uso", "`/restore ID_DEL_BACKUP`", False),
                ]
            )
            await interaction.followup.send(embed=embed)
            return

        # Buscar el backup específico
        backup_file = os.path.join(BACKUP_DIR, f"{interaction.guild.id}_{backup_id}.json")

        if not os.path.exists(backup_file):
            embed = create_embed(
                "❌ Backup no encontrado",
                f"No se encontró el backup `{backup_id}`",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
            return

        # Restaurar
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        restored = await self._restore_backup(interaction.guild, backup_data)

        embed = create_embed(
            "🔄 BACKUP RESTAURADO",
            f"Servidor **{interaction.guild.name}** restaurado exitosamente",
            color=0x00FF00,
            fields=[
                ("📊 Canales restaurados", str(restored['channels']), True),
                ("🎭 Roles restaurados", str(restored['roles']), True),
                ("📋 Reglas restauradas", str(restored.get('rules', 0)), True),
                ("⏰ Restaurado por", interaction.user.mention, True),
            ]
        )
        await interaction.followup.send(embed=embed)

        # Log
        await db.add_log(
            interaction.guild.id, "backup_restored",
            interaction.user.id,
            details=f"Backup {backup_id} restaurado — {restored['channels']} canales, {restored['roles']} roles"
        )

    @app_commands.command(name="backups", description="📋 Ver todos los backups")
    async def list_backups_cmd(self, interaction: discord.Interaction):
        """Muestra todos los backups disponibles"""
        if not await self._check_security_role(interaction):
            return

        backups = self._list_backups(interaction.guild.id)

        if not backups:
            embed = create_embed(
                "📋 Sin backups",
                "No hay backups disponibles. Usa `/backup` para crear uno.",
                color=0x00BFFF
            )
            await interaction.response.send_message(embed=embed)
            return

        backup_list = []
        for b in backups[:15]:
            backup_list.append(
                f"**{b['id']}** — {b['timestamp']}\n"
                f"  📊 {b['channels']} canales | 🎭 {b['roles']} roles | 👥 {b.get('members', 'N/A')} miembros"
            )

        embed = create_embed(
            f"📋 BACKUPS ({len(backups)} disponibles)",
            "\n\n".join(backup_list),
            color=0x00BFFF,
            fields=[
                ("💾 Total", str(len(backups)), True),
                ("📝 Uso", "`/restore ID` para restaurar", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="backupinfo", description="📊 Info de un backup específico")
    @app_commands.describe(backup_id="ID del backup")
    async def backup_info_cmd(self, interaction: discord.Interaction, backup_id: str):
        """Muestra información detallada de un backup"""
        if not await self._check_security_role(interaction):
            return

        backup_file = os.path.join(BACKUP_DIR, f"{interaction.guild.id}_{backup_id}.json")

        if not os.path.exists(backup_file):
            embed = create_embed("❌ Backup no encontrado", f"No se encontró `{backup_id}`", color=0xFF0000)
            await interaction.response.send_message(embed=embed)
            return

        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        channels = backup_data.get('channels', [])
        roles = backup_data.get('roles', [])

        embed = create_embed(
            f"📊 INFO DEL BACKUP: {backup_id}",
            f"Detalles del backup de **{interaction.guild.name}**",
            color=0x00BFFF,
            fields=[
                ("⏰ Fecha", backup_data.get('timestamp', 'N/A'), True),
                ("📊 Canales", str(len(channels)), True),
                ("🎭 Roles", str(len(roles)), True),
                ("💾 Tamaño", f"{len(json.dumps(backup_data)) / 1024:.1f} KB", True),
            ]
        )

        # Listar canales
        if channels:
            channel_names = [f"• {c['name']} ({c['type']})" for c in channels[:15]]
            embed.add_field(name="📁 Canales", value="\n".join(channel_names), inline=False)

        # Listar roles
        if roles:
            role_names = [f"• {r['name']} (pos: {r['position']})" for r in roles[:15]]
            embed.add_field(name="🎭 Roles", value="\n".join(role_names), inline=False)

        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  FUNCIONES INTERNAS
    # ═══════════════════════════════════════════

    async def _create_backup(self, guild, automatic=False):
        """Crea un backup completo del servidor"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"

        # Backup de canales
        channels = []
        for channel in guild.channels:
            channel_data = {
                'id': channel.id,
                'name': channel.name,
                'type': str(channel.type),
                'category': channel.category.name if channel.category else None,
                'topic': getattr(channel, 'topic', None),
                'position': channel.position,
                'nsfw': getattr(channel, 'nsfw', False),
            }
            channels.append(channel_data)

        # Backup de roles
        roles = []
        for role in guild.roles:
            if role == guild.default_role:
                continue
            role_data = {
                'id': role.id,
                'name': role.name,
                'color': str(role.color),
                'position': role.position,
                'hoist': role.hoist,
                'mentionable': role.mentionable,
                'permissions': role.permissions.value,
            }
            roles.append(role_data)

        # Backup de configuración
        settings = {
            'name': guild.name,
            'description': guild.description,
            'verification_level': str(guild.verification_level),
            'explicit_content_filter': str(guild.explicit_content_filter),
            'default_message_notifications': str(guild.default_message_notifications),
            'afk_channel': guild.afk_channel.name if guild.afk_channel else None,
            'afk_timeout': guild.afk_timeout,
            'icon': str(guild.icon.url) if guild.icon else None,
        }

        # Backup de reglas (si existen)
        rules = []
        if hasattr(guild, 'rules'):
            for rule in guild.rules:
                rules.append({
                    'id': rule.id,
                    'name': rule.name,
                    'trigger': str(rule.trigger),
                    'actions': [str(a) for a in rule.actions],
                })

        backup_data = {
            'id': backup_id,
            'timestamp': timestamp,
            'guild_id': guild.id,
            'guild_name': guild.name,
            'channels': channels,
            'roles': roles,
            'settings': settings,
            'rules': rules,
            'member_count': guild.member_count,
        }

        # Guardar backup
        backup_file = os.path.join(BACKUP_DIR, f"{guild.id}_{backup_id}.json")
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        # Log
        if not automatic:
            await db.add_log(
                guild.id, "backup_created",
                details=f"Backup creado — {len(channels)} canales, {len(roles)} roles"
            )

        return backup_data

    async def _restore_backup(self, guild, backup_data):
        """Restaura el servidor desde un backup"""
        restored = {'channels': 0, 'roles': 0, 'rules': 0}

        # Restaurar roles (en orden inverso de posición)
        roles_data = sorted(backup_data.get('roles', []), key=lambda x: x['position'], reverse=True)
        existing_roles = {r.name: r for r in guild.roles}

        for role_data in roles_data:
            if role_data['name'] not in existing_roles:
                try:
                    await guild.create_role(
                        name=role_data['name'],
                        color=discord.Color(int(role_data['color'].replace('#', ''), 16)),
                        hoist=role_data.get('hoist', False),
                        mentionable=role_data.get('mentionable', False),
                        reason="Backup restore"
                    )
                    restored['roles'] += 1
                except discord.Forbidden:
                    pass

        # Restaurar canales
        channels_data = sorted(backup_data.get('channels', []), key=lambda x: x['position'])
        existing_channels = {c.name: c for c in guild.channels}

        for channel_data in channels_data:
            if channel_data['name'] not in existing_channels:
                try:
                    channel_type = channel_data['type']
                    if 'text' in channel_type or 'announcements' in channel_type:
                        await guild.create_text_channel(
                            name=channel_data['name'],
                            topic=channel_data.get('topic'),
                            nsfw=channel_data.get('nsfw', False),
                            reason="Backup restore"
                        )
                    elif 'voice' in channel_type:
                        await guild.create_voice_channel(
                            name=channel_data['name'],
                            reason="Backup restore"
                        )
                    elif 'category' in channel_type:
                        await guild.create_category(
                            name=channel_data['name'],
                            reason="Backup restore"
                        )
                    restored['channels'] += 1
                except discord.Forbidden:
                    pass

        return restored

    def _list_backups(self, guild_id):
        """Lista todos los backups de un servidor"""
        backups = []
        prefix = f"{guild_id}_backup_"

        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith(prefix) and filename.endswith('.json'):
                filepath = os.path.join(BACKUP_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    backup_id = filename.replace(f"{guild_id}_", "").replace('.json', '')
                    backups.append({
                        'id': backup_id,
                        'timestamp': data.get('timestamp', 'N/A'),
                        'channels': len(data.get('channels', [])),
                        'roles': len(data.get('roles', [])),
                        'members': data.get('member_count', 'N/A'),
                    })
                except Exception:
                    pass

        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups

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
    await bot.add_cog(BackupCog(bot))
