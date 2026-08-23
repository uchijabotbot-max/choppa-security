"""
cogs/info.py — Comandos de Información v6
Owner, ServerAudit, WhoIs, Help, Ping, Whitelist, Blacklist
"""
import discord
from discord.ext import commands
from discord import app_commands
import platform
import psutil
from datetime import datetime

from config import (
    OWNER_ID, OWNER_NAME, OWNER_DISCORD, SECURITY_ROLES,
    BOT_NAME, BOT_VERSION, BOT_FOOTER, COLOR_RED, COLOR_GREEN, COLOR_BLUE, COLOR_YELLOW
)
from utils.embeds import create_embed, owner_info, server_audit, whois_embed, security_status
from database import db


class Info(commands.Cog):
    """Comandos de información"""

    def __init__(self, bot):
        self.bot = bot

    # ═══════════════════════════════════════════
    #  OWNER / CREADOR
    # ═══════════════════════════════════════════

    @app_commands.command(name="owner", description="Información del creador del bot")
    async def owner_cmd(self, interaction: discord.Interaction):
        embed = owner_info()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="creator", description="Alias de /owner")
    async def creator_cmd(self, interaction: discord.Interaction):
        embed = owner_info()
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  SERVER AUDIT
    # ═══════════════════════════════════════════

    @app_commands.command(name="serveraudit", description="Auditoría completa del servidor")
    async def serveraudit_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild

        # Recopilar info
        member_count = guild.member_count
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
        channels = len(guild.channels)
        roles = len(guild.roles)
        emojis = len(guild.emojis)
        boosts = guild.premium_subscription_count or 0
        boost_level = guild.premium_tier

        embed = server_audit(guild, member_count, online, channels, roles, emojis, boost_level)

        # Info adicional
        inv_count = 0
        try:
            invites = await guild.invites()
            inv_count = len(invites)
        except discord.Forbidden:
            pass

        embed.add_field(name="🔗 Invitaciones", value=str(inv_count), inline=True)
        embed.add_field(name="🚀 Boosts", value=f"{boosts} (Nivel {boost_level})", inline=True)
        embed.add_field(name="🔒 Verificación", value=str(guild.verification_level).title(), inline=True)

        # Canary traps / whitelist count
        bl = await db.get_blacklist(guild.id)
        wl = await db.get_whitelist(guild.id)
        embed.add_field(name="黑名单 Blacklist", value=str(len(bl)), inline=True)
        embed.add_field(name="🛡️ Whitelist", value=str(len(wl)), inline=True)

        await interaction.followup.send(embed=embed)

    # ═══════════════════════════════════════════
    #  WHOIS
    # ═══════════════════════════════════════════

    @app_commands.command(name="whois", description="Información detallada de un usuario")
    @app_commands.describe(user="Usuario a investigar")
    async def whois_cmd(self, interaction: discord.Interaction, user: discord.Member):
        warn_count = await db.get_warn_count(interaction.guild.id, user.id)
        is_bl = await db.is_blacklisted(interaction.guild.id, user.id)
        is_wl = await db.is_whitelisted(interaction.guild.id, user.id)
        embed = whois_embed(user, warn_count, is_bl, is_wl)
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  PING
    # ═══════════════════════════════════════════

    @app_commands.command(name="ping", description="Ver latencia del bot")
    async def ping_cmd(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = create_embed("🏓 PONG", f"Latencia: **{latency}ms**", COLOR_GREEN,
            [("🤖 Bot", f"{self.bot.user.name}", True),
             ("⏱️ WebSocket", f"{latency}ms", True),
             ("📊 Servidores", str(len(self.bot.guilds)), True)])
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  BOT INFO
    # ═══════════════════════════════════════════

    @app_commands.command(name="botinfo", description="Información del bot")
    async def botinfo_cmd(self, interaction: discord.Interaction):
        embed = create_embed(
            f"🤖 {BOT_NAME}",
            f"Bot de seguridad avanzado para Discord",
            COLOR_BLUE,
            fields=[
                ("📋 Versión", BOT_VERSION, True),
                ("📊 Servidores", str(len(self.bot.guilds)), True),
                ("👥 Usuarios", str(sum(g.member_count for g in self.bot.guilds)), True),
                ("⏱️ Latencia", f"{round(self.bot.latency * 1000)}ms", True),
                ("🐍 Python", platform.python_version(), True),
                ("📚 discord.py", discord.__version__, True),
                ("💾 RAM", f"{psutil.virtual_memory().percent}%", True),
                ("🖥️ Sistema", platform.system(), True),
                ("👑 Creador", OWNER_NAME, True),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  HELP
    # ═══════════════════════════════════════════

    @app_commands.command(name="help", description="Panel de todos los comandos")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = create_embed(
            f"📋 COMANDOS DE {BOT_NAME.upper()}",
            "Todos los comandos disponibles",
            COLOR_BLUE,
            fields=[
                ("🛡️ Seguridad", "• `/security` — Estado de seguridad\n• `/raid` — Config anti-raid\n• `/antispam` — Config anti-spam", False),
                ("🔨 Moderación", "• `/warn` — Advertir usuario\n• `/warns` — Ver advertencias\n• `/clearwarns` — Limpiar warns\n• `/ban` — Banear usuario\n• `/unban` — Desbanear\n• `/kick` — Expulsar\n• `/mute` — Silenciar\n• `/unmute` — Quitar silencio", False),
                ("📊 Información", "• `/whois` — Info de usuario\n• `/serveraudit` — Auditoría del servidor\n• `/botinfo` — Info del bot\n• `/ping` — Latencia", False),
                ("👑 Creador", "• `/owner` — Info del creador", False),
                ("⚙️ Config", "• `/setlog` — Canal de logs\n• `/blacklist` — Blacklist\n• `/whitelist` — Whitelist", False),
                ("📋 Protecciones Activas", "🚨 Anti-Raid\n🚫 Anti-Spam\n⚡ Anti-Flood\n🔗 Anti-Links\n🎣 Anti-Phishing\n🚫 Anti-NSFW\n📢 Anti-Menciones\n🤖 Anti-Bots\n🔠 Auto-Mod\n🔍 Anti-Alt Accounts", False),
            ]
        )
        await interaction.response.send_message(embed=embed)

    # ═══════════════════════════════════════════
    #  BLACKLIST
    # ═══════════════════════════════════════════

    @app_commands.command(name="blacklist", description="Agregar usuario a la blacklist (auto-ban)")
    @app_commands.describe(user="Usuario", reason="Razón")
    async def blacklist_cmd(self, interaction: discord.Interaction, user: discord.Member, reason: str = "Sin razón"):
        if not self._check_role(interaction): return
        await db.add_blacklist(interaction.guild.id, user.id, reason)
        try:
            await user.ban(reason=f"Blacklist: {reason}")
        except discord.Forbidden:
            pass
        await self._dm(user, "黑名单 BLACKLIST",
            f"Fuiste agregado a la blacklist de **{interaction.guild.name}**",
            COLOR_RED, [("📝 Razón", reason, False)])
        await interaction.response.send_message(embed=create_embed("✅ BLACKLIST",
            f"**{user.mention}** agregado a la blacklist y baneado", COLOR_RED,
            [("👤 Usuario", user.mention, True), ("📝 Razón", reason, True)]))

    @app_commands.command(name="unblacklist", description="Remover usuario de la blacklist")
    @app_commands.describe(user_id="ID del usuario")
    async def unblacklist_cmd(self, interaction: discord.Interaction, user_id: str):
        if not self._check_role(interaction): return
        await db.remove_blacklist(interaction.guild.id, int(user_id))
        await interaction.response.send_message(embed=create_embed("✅ BLACKLIST REMOVIDA",
            f"Usuario `{user_id}` removido de la blacklist", COLOR_GREEN))

    # ═══════════════════════════════════════════
    #  WHITELIST
    # ═══════════════════════════════════════════

    @app_commands.command(name="whitelist", description="Agregar usuario a la whitelist (inmune a todo)")
    @app_commands.describe(user="Usuario")
    async def whitelist_cmd(self, interaction: discord.Interaction, user: discord.Member):
        if not self._check_role(interaction): return
        await db.add_whitelist(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=create_embed("✅ WHITELIST",
            f"**{user.mention}** ahora es **INMUNE** a todo el auto-mod", COLOR_GREEN,
            [("👤 Usuario", user.mention, True),
             ("🛡️ Estado", "INMUNE A TODO", True),
             ("📝 Incluye", "Anti-spam, anti-links, auto-mod", False)]))

    @app_commands.command(name="unwhitelist", description="Remover usuario de la whitelist")
    @app_commands.describe(user_id="ID del usuario")
    async def unwhitelist_cmd(self, interaction: discord.Interaction, user_id: str):
        if not self._check_role(interaction): return
        await db.remove_whitelist(interaction.guild.id, int(user_id))
        await interaction.response.send_message(embed=create_embed("✅ WHITELIST REMOVIDA",
            f"Usuario `{user_id}` ya no es inmune", COLOR_YELLOW))

    @app_commands.command(name="wl", description="Ver whitelist completa")
    async def wl_cmd(self, interaction: discord.Interaction):
        wl = await db.get_whitelist(interaction.guild.id)
        if not wl:
            return await interaction.response.send_message(embed=create_embed("✅ Whitelist", "Vacía.", COLOR_GREEN))
        lines = []
        for entry in wl:
            member = interaction.guild.get_member(entry[2])
            lines.append(f"• {member.mention if member else f'`{entry[2]}`'}")
        await interaction.response.send_message(embed=create_embed("✅ Whitelist",
            "\n".join(lines[:20]), COLOR_GREEN,
            [("👥 Total", str(len(wl)), True)]))

    # ═══════════════════════════════════════════
    #  LOGS
    # ═══════════════════════════════════════════

    @app_commands.command(name="logs", description="Ver logs de seguridad recientes")
    @app_commands.describe(event_type="Tipo de evento (opcional)")
    async def logs_cmd(self, interaction: discord.Interaction, event_type: str = None):
        if not self._check_role(interaction): return
        logs = await db.get_logs(interaction.guild.id, limit=15, event_type=event_type)
        if not logs:
            return await interaction.response.send_message(embed=create_embed("📋 Logs", "No hay logs recientes.", COLOR_GREEN))

        lines = []
        for log in logs:
            ts = f"<t:{int(datetime.fromisoformat(log[6]).timestamp())}:R>" if log[6] else "N/A"
            user = f"<@{log[3]}>" if log[3] else "Auto"
            lines.append(f"**{log[2]}** por {user} — {ts}")

        await interaction.response.send_message(embed=create_embed("📋 Logs de Seguridad",
            "\n".join(lines), COLOR_BLUE,
            [("📊 Total", str(len(logs)), True)]))

    # ═══════════════════════════════════════════
    #  ANTI-EXTENSIÓN / APLICACIONES
    # ═══════════════════════════════════════════

    @app_commands.command(name="extensions", description="Ver todas las integraciones/apps del servidor")
    async def extensions_cmd(self, interaction: discord.Interaction):
        if not self._check_role(interaction): return
        await interaction.response.defer()
        guild = interaction.guild

        fields = []

        # Bots
        bots = [m for m in guild.members if m.bot and m != self.bot.user]
        bot_list = "\n".join([f"• {b.mention} (`{b.id}`)" for b in bots[:15]]) or "Ninguno"
        fields.append(("🤖 Bots", f"Total: **{len(bots)}**\n{bot_list}", False))

        # Webhooks
        webhook_count = 0
        webhook_info = []
        for ch in guild.text_channels:
            try:
                whs = await ch.webhooks()
                webhook_count += len(whs)
                for wh in whs[:3]:
                    webhook_info.append(f"• #{ch.name}: `{wh.name}`")
            except discord.Forbidden:
                pass
        fields.append(("🔗 Webhooks", f"Total: **{webhook_count}**\n" + "\n".join(webhook_info[:10]) or "Ninguno", False))

        # Integraciones (slash commands de otros bots)
        try:
            integrations = await guild.integrations()
            int_list = []
            for i in integrations[:10]:
                type_str = "App" if hasattr(i, 'application') else "Integration"
                int_list.append(f"• **{i.name}** ({type_str})")
            fields.append(("📦 Integraciones", f"Total: **{len(integrations)}**\n" + "\n".join(int_list) or "Ninguno", False))
        except discord.Forbidden:
            fields.append(("📦 Integraciones", "Sin permisos para ver", False))

        # Emojis y Stickers
        emoji_count = len(guild.emojis)
        sticker_count = len(guild.stickers) if hasattr(guild, 'stickers') else 0
        fields.append(("😀 Emojis", str(emoji_count), True))
        fields.append(("🏷️ Stickers", str(sticker_count), True))

        # Roles
        roles = [r for r in guild.roles if r.name != '@everyone' and r != guild.default_role]
        dangerous = []
        for r in roles:
            perms = [p for p, v in r.permissions if v and p in ['administrator', 'ban_members', 'kick_members', 'manage_guild', 'manage_channels', 'manage_roles', 'manage_webhooks']]
            if perms:
                dangerous.append(f"⚠️ {r.name}: `{', '.join(perms)}`")

        fields.append(("🎭 Roles Totales", str(len(roles)), True))
        if dangerous:
            fields.append(("🚨 Roles con Permisos Peligrosos", "\n".join(dangerous[:10]), False))

        # Invites
        try:
            invites = await guild.invites()
            fields.append(("🔗 Invitaciones", str(len(invites)), True))
        except discord.Forbidden:
            fields.append(("🔗 Invitaciones", "Sin permisos", True))

        embed = create_embed(
            "🔌 EXTENSIONES / APLICACIONES",
            f"Todas las integraciones de **{guild.name}**",
            COLOR_BLUE,
            fields=fields
        )
        await interaction.followup.send(embed=embed)

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


async def setup(bot):
    await bot.add_cog(Info(bot))
