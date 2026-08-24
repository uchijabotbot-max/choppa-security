"""
cogs/advanced.py — Features Avanzadas v6
Verification, Auto-Role, Welcome, Goodbye, Lockdown, Server Stats, Slowmode, Reaction Roles
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os

from config import (
    SECURITY_ROLES, BOT_NAME, BOT_VERSION, BOT_FOOTER, BOT_IMAGE,
    OWNER_ID, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_ORANGE,
    COLOR_PRIMARY
)
from utils.embeds import create_embed
from database import db


class Advanced(commands.Cog):
    """Features avanzadas del bot"""

    def __init__(self, bot):
        self.bot = bot
        self.verification_pending = {}
        self.reaction_roles = {}
        self._load_reaction_roles()
        self.stats_loop.start()

    def cog_unload(self):
        self.stats_loop.cancel()

    def _load_reaction_roles(self):
        """Carga reaction roles desde archivo"""
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reaction_roles.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    self.reaction_roles = json.load(f)
            except:
                self.reaction_roles = {}

    def _save_reaction_roles(self):
        """Guarda reaction roles en archivo"""
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reaction_roles.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.reaction_roles, f, indent=2)

    # ==========================================
    #  SERVER STATS (auto-update cada 5 min)
    # ==========================================

    @tasks.loop(minutes=5)
    async def stats_loop(self):
        """Actualiza stats del servidor en canales"""
        try:
            for guild in self.bot.guilds:
                settings = await db.get_settings(guild.id) or {}

                # Actualizar miembros
                member_channel_id = settings.get("stats_members_channel")
                if member_channel_id:
                    ch = guild.get_channel(member_channel_id)
                    if ch:
                        try:
                            await ch.edit(name="👥 Miembros: " + str(guild.member_count))
                        except:
                            pass

                # Actualizar canales
                channel_channel_id = settings.get("stats_channels_channel")
                if channel_channel_id:
                    ch = guild.get_channel(channel_channel_id)
                    if ch:
                        try:
                            await ch.edit(name="📁 Canales: " + str(len(guild.channels)))
                        except:
                            pass

                # Actualizar roles
                role_channel_id = settings.get("stats_roles_channel")
                if role_channel_id:
                    ch = guild.get_channel(role_channel_id)
                    if ch:
                        try:
                            await ch.edit(name="🎭 Roles: " + str(len(guild.roles)))
                        except:
                            pass

                # Actualizar online
                online_channel_id = settings.get("stats_online_channel")
                if online_channel_id:
                    ch = guild.get_channel(online_channel_id)
                    if ch:
                        try:
                            online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
                            await ch.edit(name="🟢 En linea: " + str(online))
                        except:
                            pass

                # Actualizar bots
                bots_channel_id = settings.get("stats_bots_channel")
                if bots_channel_id:
                    ch = guild.get_channel(bots_channel_id)
                    if ch:
                        try:
                            bots = sum(1 for m in guild.members if m.bot)
                            await ch.edit(name="🤖 Bots: " + str(bots))
                        except:
                            pass

        except Exception as e:
            pass

    @stats_loop.before_loop
    async def before_stats(self):
        await self.bot.wait_until_ready()

    # ==========================================
    #  VERIFICATION SYSTEM
    # ==========================================

    @app_commands.command(name="verify", description="Configurar sistema de verificacion")
    @app_commands.describe(channel="Canal de verificacion", role="Rol a dar al verificar")
    async def verify_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        if not self._check_role(interaction):
            return

        await db.update_settings(interaction.guild.id,
            verify_channel_id=channel.id,
            verify_role_id=role.id
        )

        # Enviar embed de verificacion
        embed = create_embed(
            "🔒 VERIFICATE",
            "Haz clic en el boton de abajo para verificar que no eres un bot.",
            COLOR_BLUE,
            [("📍 Canal", channel.mention, True),
             ("🎭 Rol que recibiras", role.mention, True),
             ("💡 Instrucciones", "Haz clic en el boton y recibiras el rol automaticamente", False)])

        view = VerifyView(self.bot, role)
        try:
            await channel.send(embed=embed, view=view)
        except:
            pass

        await interaction.response.send_message(embed=create_embed(
            "✅ VERIFICACION CONFIGURADA",
            "Sistema de verificacion activo en " + channel.mention,
            COLOR_GREEN,
            [("📍 Canal", channel.mention, True),
             ("🎭 Rol", role.mention, True)]))

    # ==========================================
    #  AUTO-ROLE
    # ==========================================

    @app_commands.command(name="autorole", description="Configurar rol automatico al entrar")
    @app_commands.describe(role="Rol a asignar automaticamente")
    async def autorole_cmd(self, interaction: discord.Interaction, role: discord.Role):
        if not self._check_role(interaction):
            return

        await db.update_settings(interaction.guild.id, autorole_id=role.id)

        await interaction.response.send_message(embed=create_embed(
            "✅ AUTO-ROLE CONFIGURADO",
            "Todos los miembros nuevos recibiran " + role.mention + " automaticamente",
            COLOR_GREEN,
            [("🎭 Rol", role.mention, True),
             ("👥 Miembros actuales", "No se asigna retroactivamente", False)]))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        guild = member.guild
        settings = await db.get_settings(guild.id) or {}

        # Auto-role
        autorole_id = settings.get("autorole_id")
        if autorole_id:
            role = guild.get_role(autorole_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role: rol asignado automaticamente")
                except:
                    pass

        # Welcome message
        welcome_channel_id = settings.get("welcome_channel_id")
        if welcome_channel_id:
            ch = guild.get_channel(welcome_channel_id)
            if ch:
                welcome_msg = settings.get("welcome_message", "Bienvenido a **{server}**, {user}! 🎉")
                welcome_msg = welcome_msg.replace("{server}", guild.name).replace("{user}", member.mention).replace("{count}", str(guild.member_count))

                embed = create_embed(
                    "🎉 BIENVENIDO",
                    welcome_msg,
                    COLOR_GREEN,
                    [("👤 Usuario", member.mention + "\n`" + str(member.id) + "`", True),
                     ("📅 Cuenta creada", "<t:" + str(int(member.created_at.timestamp())) + ":R>", True),
                     ("👥 Miembros", str(guild.member_count), True)])
                try:
                    await ch.send(embed=embed)
                except:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return

        guild = member.guild
        settings = await db.get_settings(guild.id) or {}

        # Goodbye message
        goodbye_channel_id = settings.get("goodbye_channel_id")
        if goodbye_channel_id:
            ch = guild.get_channel(goodbye_channel_id)
            if ch:
                goodbye_msg = settings.get("goodbye_message", "Adios **{user}**, te extrañaremos! 👋")
                goodbye_msg = goodbye_msg.replace("{user}", str(member)).replace("{server}", guild.name).replace("{count}", str(guild.member_count - 1))

                embed = create_embed(
                    "👋 ADIOS",
                    goodbye_msg,
                    COLOR_YELLOW,
                    [("👤 Usuario", str(member) + "\n`" + str(member.id) + "`", True),
                     ("👥 Miembros restantes", str(guild.member_count - 1), True)])
                try:
                    await ch.send(embed=embed)
                except:
                    pass

    # ==========================================
    #  WELCOME / GOODBYE CONFIG
    # ==========================================

    @app_commands.command(name="welcome", description="Configurar canal de bienvenida")
    @app_commands.describe(channel="Canal para bienvenidas", message="Mensaje (usa {user}, {server}, {count})")
    async def welcome_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str = "Bienvenido a **{server}**, {user}! 🎉"):
        if not self._check_role(interaction):
            return

        await db.update_settings(interaction.guild.id,
            welcome_channel_id=channel.id,
            welcome_message=message
        )

        await interaction.response.send_message(embed=create_embed(
            "✅ BIENVENIDA CONFIGURADA",
            "Mensajes de bienvenida en " + channel.mention,
            COLOR_GREEN,
            [("📍 Canal", channel.mention, True),
             ("📝 Mensaje", message, False),
             ("💡 Variables", "{user} = mencion\n{server} = nombre del server\n{count} = total miembros", False)]))

    @app_commands.command(name="goodbye", description="Configurar canal de despedida")
    @app_commands.describe(channel="Canal para despedidas", message="Mensaje (usa {user}, {server}, {count})")
    async def goodbye_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str = "Adios **{user}**, te extrañaremos! 👋"):
        if not self._check_role(interaction):
            return

        await db.update_settings(interaction.guild.id,
            goodbye_channel_id=channel.id,
            goodbye_message=message
        )

        await interaction.response.send_message(embed=create_embed(
            "✅ DESPEDIDA CONFIGURADA",
            "Mensajes de despedida en " + channel.mention,
            COLOR_GREEN,
            [("📍 Canal", channel.mention, True),
             ("📝 Mensaje", message, False),
             ("💡 Variables", "{user} = nombre\n{server} = nombre del server\n{count} = total miembros", False)]))

    # ==========================================
    #  LOCKDOWN / UNLOCK
    # ==========================================

    @app_commands.command(name="lockdown", description="Cerrar TODOS los canales (emergencia)")
    @app_commands.describe(reason="Razon del lockdown")
    async def lockdown_cmd(self, interaction: discord.Interaction, reason: str = "Lockdown de emergencia"):
        if not self._check_role(interaction):
            return
        await interaction.response.defer()

        locked = 0
        for ch in interaction.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = False
                await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite,
                                         reason="Lockdown: " + reason)
                locked += 1
            except:
                pass

        # Desbloquear canales de admin
        for ch in interaction.guild.text_channels:
            if ch.name in ["security-logs", "admin-chat", "staff", "general"]:
                try:
                    overwrite = ch.overwrites_for(interaction.guild.default_role)
                    overwrite.send_messages = True
                    await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite)
                except:
                    pass

        await interaction.followup.send(embed=create_embed(
            "🔒 LOCKDOWN ACTIVADO",
            "Todos los canales han sido cerrados",
            COLOR_RED,
            [("🔒 Canales cerrados", str(locked), True),
             ("📝 Razon", reason, False),
             ("👤 Activado por", interaction.user.mention, True),
             ("💡 Para desbloquear", "Usa `/unlock`", True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)]))

        # Log
        await db.add_log(interaction.guild.id, "lockdown", interaction.user.id, details="Razon: " + reason)

    @app_commands.command(name="unlock", description="Abrir TODOS los canales")
    async def unlock_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction):
            return
        await interaction.response.defer()

        unlocked = 0
        for ch in interaction.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(interaction.guild.default_role)
                overwrite.send_messages = None
                await ch.set_permissions(interaction.guild.default_role, overwrite=overwrite,
                                         reason="Unlock")
                unlocked += 1
            except:
                pass

        await interaction.followup.send(embed=create_embed(
            "🔓 UNLOCK ACTIVADO",
            "Todos los canales han sido abiertos",
            COLOR_GREEN,
            [("🔓 Canales abiertos", str(unlocked), True),
             ("👤 Desbloqueado por", interaction.user.mention, True),
             ("🕐 Hora", "<t:" + str(int(datetime.utcnow().timestamp())) + ":F>", True)]))

        await db.add_log(interaction.guild.id, "unlock", interaction.user.id)

    # ==========================================
    #  SERVER STATS CONFIG
    # ==========================================

    @app_commands.command(name="serverstats", description="Configurar canales de stats del servidor")
    @app_commands.describe(members_channel="Canal para count de miembros", channels_channel="Canal para count de canales", roles_channel="Canal para count de roles", online_channel="Canal para count de online")
    async def serverstats_cmd(self, interaction: discord.Interaction,
                               members_channel: discord.TextChannel = None,
                               channels_channel: discord.TextChannel = None,
                               roles_channel: discord.TextChannel = None,
                               online_channel: discord.TextChannel = None):
        if not self._check_role(interaction):
            return

        updates = {}
        if members_channel:
            updates["stats_members_channel"] = members_channel.id
        if channels_channel:
            updates["stats_channels_channel"] = channels_channel.id
        if roles_channel:
            updates["stats_roles_channel"] = roles_channel.id
        if online_channel:
            updates["stats_online_channel"] = online_channel.id

        if updates:
            await db.update_settings(interaction.guild.id, **updates)

        fields = []
        if members_channel:
            fields.append(("👥 Miembros", members_channel.mention, True))
        if channels_channel:
            fields.append(("📁 Canales", channels_channel.mention, True))
        if roles_channel:
            fields.append(("🎭 Roles", roles_channel.mention, True))
        if online_channel:
            fields.append(("🟢 En linea", online_channel.mention, True))

        if not fields:
            fields.append(("📝 Instrucciones", "Menciona los canales que quieres usar para cada stat", False))

        await interaction.response.send_message(embed=create_embed(
            "📊 SERVER STATS CONFIGURADO",
            "Canales de estadisticas del servidor",
            COLOR_GREEN, fields))

    # ==========================================
    #  SLOWMODE
    # ==========================================

    @app_commands.command(name="slowmode", description="Establecer slowmode en un canal")
    @app_commands.describe(channel="Canal", seconds="Segundos de slowmode (0 = desactivar)")
    async def slowmode_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, seconds: int = 0):
        if not self._check_role(interaction):
            return

        try:
            await channel.edit(slowmode_delay=seconds)
            if seconds > 0:
                msg = "Slowmode de **" + str(seconds) + "s** activado en " + channel.mention
                color = COLOR_YELLOW
            else:
                msg = "Slowmode desactivado en " + channel.mention
                color = COLOR_GREEN

            await interaction.response.send_message(embed=create_embed(
                "⏱️ SLOWMODE", msg, color,
                [("📍 Canal", channel.mention, True),
                 ("⏱️ Segundos", str(seconds), True)]))
        except:
            await interaction.response.send_message(embed=create_embed(
                "❌ Error", "No pude cambiar el slowmode.", COLOR_RED))

    # ==========================================
    #  REACTION ROLES
    # ==========================================

    @app_commands.command(name="reactionrole", description="Crear reaction role")
    @app_commands.describe(channel="Canal del mensaje", emoji="Emoji para el rol", role="Rol a asignar", message_id="ID del mensaje (opcional)")
    async def reactionrole_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel, emoji: str, role: discord.Role, message_id: str = None):
        if not self._check_role(interaction):
            return

        guild_id = str(interaction.guild.id)

        if guild_id not in self.reaction_roles:
            self.reaction_roles[guild_id] = []

        self.reaction_roles[guild_id].append({
            "channel_id": channel.id,
            "emoji": emoji,
            "role_id": role.id,
            "message_id": int(message_id) if message_id else None
        })
        self._save_reaction_roles()

        # Si no hay message_id, crear mensaje
        if not message_id:
            embed = create_embed(
                "🎭 REACTION ROLES",
                "Reacciona para obtener roles!",
                COLOR_BLUE,
                [(emoji, role.mention, True)])

            try:
                msg = await channel.send(embed=embed)
                await msg.add_reaction(emoji)
                # Actualizar message_id
                self.reaction_roles[guild_id][-1]["message_id"] = msg.id
                self._save_reaction_roles()
            except:
                pass

        await interaction.response.send_message(embed=create_embed(
            "✅ REACTION ROLE CREADO",
            "Reacciona " + emoji + " para obtener " + role.mention,
            COLOR_GREEN,
            [("🎭 Emoji", emoji, True),
             ("📍 Canal", channel.mention, True),
             ("👤 Rol", role.mention, True)]))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Asigna rol cuando alguien reacciona"""
        if payload.member.bot:
            return

        guild_id = str(payload.guild_id)
        if guild_id not in self.reaction_roles:
            return

        for rr in self.reaction_roles[guild_id]:
            if rr["message_id"] == payload.message_id and rr["emoji"] == str(payload.emoji.name):
                guild = self.bot.get_guild(payload.guild_id)
                role = guild.get_role(rr["role_id"])
                if role:
                    try:
                        await payload.member.add_roles(role, reason="Reaction role")
                    except:
                        pass
                return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Remueve rol cuando alguien quita la reaccion"""
        guild_id = str(payload.guild_id)
        if guild_id not in self.reaction_roles:
            return

        for rr in self.reaction_roles[guild_id]:
            if rr["message_id"] == payload.message_id and rr["emoji"] == str(payload.emoji.name):
                guild = self.bot.get_guild(payload.guild_id)
                member = guild.get_member(payload.user_id)
                if member and not member.bot:
                    role = guild.get_role(rr["role_id"])
                    if role:
                        try:
                            await member.remove_roles(role, reason="Reaction role removed")
                        except:
                            pass
                return

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


# ==========================================
#  VERIFY VIEW (Button)
# ==========================================

class VerifyView(discord.ui.View):
    def __init__(self, bot, role):
        super().__init__(timeout=None)
        self.bot = bot
        self.role = role

    @discord.ui.button(label="Verificarme", style=discord.ButtonStyle.green, emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.add_roles(self.role, reason="Verificado")
            await interaction.response.send_message(
                embed=create_embed("✅ VERIFICADO",
                    "Has sido verificado correctamente! Ahora tienes acceso a todos los canales.",
                    COLOR_GREEN,
                    [("🎭 Rol", self.role.mention, True),
                     ("📍 Servidor", interaction.guild.name, True)]),
                ephemeral=True)
        except:
            await interaction.response.send_message(
                embed=create_embed("❌ Error", "No pude darte el rol. Contacta a un admin.", COLOR_RED),
                ephemeral=True)


async def setup(bot):
    await bot.add_cog(Advanced(bot))
