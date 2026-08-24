"""
cogs/dashboard.py - Dashboard en Tiempo Real
Muestra stats del bot en un canal especifico con embeds bonitos
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import psutil
import platform

from config import BOT_NAME, BOT_VERSION, BOT_FOOTER, BOT_IMAGE, COLOR_PRIMARY, COLOR_GREEN, COLOR_BLUE, COLOR_RED, COLOR_YELLOW
from utils.embeds import create_embed
from database import db


# Configuracion del dashboard
DASHBOARD_GUILD_ID = 1477151247214579904
DASHBOARD_CHANNEL_ID = 1541190359214858290
UPDATE_INTERVAL_MINUTES = 5


class Dashboard(commands.Cog):
    """Dashboard en tiempo real del bot"""

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.commands_used = 0
        self.threats_blocked = 0
        self.last_message = None
        self.dashboard_loop.start()

    def cog_unload(self):
        self.dashboard_loop.cancel()

    @commands.Cog.listener()
    async def on_app_command(self, interaction, command):
        self.commands_used += 1

    @tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)
    async def dashboard_loop(self):
        """Actualiza el dashboard cada 5 minutos"""
        try:
            guild = self.bot.get_guild(DASHBOARD_GUILD_ID)
            if not guild:
                return
            channel = guild.get_channel(DASHBOARD_CHANNEL_ID)
            if not channel:
                return

            embed = await self._build_dashboard(guild)
            if self.last_message:
                try:
                    await self.last_message.edit(embed=embed)
                    return
                except discord.NotFound:
                    pass
            self.last_message = await channel.send(embed=embed)
        except Exception as e:
            print(f"Dashboard error: {e}")

    @dashboard_loop.before_loop
    async def before_dashboard(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.threats_blocked += 0

    # ==========================================
    #  COMANDOS
    # ==========================================

    @commands.hybrid_command(name="dashboard", description="Mostrar dashboard del bot")
    async def dashboard_cmd(self, ctx):
        """Muestra el dashboard actual"""
        guild = ctx.guild
        embed = await self._build_dashboard(guild)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="stats", description="Estadisticas del bot")
    async def stats_cmd(self, ctx):
        """Muestra estadisticas detalladas"""
        uptime = datetime.utcnow() - self.start_time
        uptime_str = self._format_uptime(uptime)

        total_users = sum(g.member_count for g in self.bot.guilds)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)
        total_roles = sum(len(g.roles) for g in self.bot.guilds)

        # Stats de la base de datos
        all_warns = 0
        all_logs = 0
        all_blacklist = 0
        all_whitelist = 0
        for g in self.bot.guilds:
            settings = await db.get_settings(g.id)
            if settings:
                all_blacklist += len(await db.get_blacklist(g.id))
                all_whitelist += len(await db.get_whitelist(g.id))

        embed = create_embed(
            "📊 ESTADISTICAS COMPLETAS",
            "Estadisticas detalladas de **" + BOT_NAME + "**",
            COLOR_BLUE,
            fields=[
                ("🤖 Bot", "Nombre: **" + self.bot.user.name + "**\nID: `" + str(self.bot.user.id) + "`\nVersion: " + BOT_VERSION, False),
                ("\u23f1\ufe0f Uptime", uptime_str, True),
                ("📊 Uso", "Comandos usados: **" + str(self.commands_used) + "**\nAmenazas bloqueadas: **" + str(self.threats_blocked) + "**", False),
                ("👥 Miembros", "**" + str(total_users) + "** en " + str(len(self.bot.guilds)) + " servidores", True),
                ("📁 Canales", "**" + str(total_channels) + "** canales totales", True),
                ("🎭 Roles", "**" + str(total_roles) + "** roles totales", True),
                ("黑名单 Blacklist", "**" + str(all_blacklist) + "** usuarios baneados", True),
                ("🛡️ Whitelist", "**" + str(all_whitelist) + "** usuarios inmunes", True),
                ("💻 Sistema", "Python " + platform.python_version() + "\ndiscord.py " + discord.__version__ + "\nRAM: " + str(psutil.virtual_memory().percent) + "%", False),
            ]
        )
        await ctx.send(embed=embed)

    # ==========================================
    #  BUILD DASHBOARD
    # ==========================================

    async def _build_dashboard(self, guild):
        """Construye el embed del dashboard"""
        uptime = datetime.utcnow() - self.start_time
        uptime_str = self._format_uptime(uptime)
        total_users = sum(g.member_count for g in self.bot.guilds)

        # Calcular menaceas bloqueadas
        total_logs = 0
        for g in self.bot.guilds:
            logs = await db.get_logs(g.id, limit=9999)
            total_logs += len(logs)

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🛡️ " + BOT_NAME + " - Dashboard en Tiempo Real",
            description="Estadisticas actualizadas cada " + str(UPDATE_INTERVAL_MINUTES) + " minutos",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )

        # Imagen del bot
        embed.set_image(url=BOT_IMAGE)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Info del bot
        embed.add_field(
            name="🤖 Bot",
            value="**" + self.bot.user.name + "**\nVersion: " + BOT_VERSION + "\nID: `" + str(self.bot.user.id) + "`",
            inline=True
        )

        # Uptime
        embed.add_field(
            name="⏱️ Uptime",
            value="**" + uptime_str + "**",
            inline=True
        )

        # Latencia
        color_latency = "🟢" if latency < 200 else ("🟡" if latency < 500 else "🔴")
        embed.add_field(
            name=color_latency + " Latencia",
            value="**" + str(latency) + "ms**",
            inline=True
        )

        # Servidores
        embed.add_field(
            name="🏠 Servidores",
            value="**" + str(len(self.bot.guilds)) + "** servidores",
            inline=True
        )

        # Miembros
        embed.add_field(
            name="👥 Miembros Total",
            value="**" + str(total_users) + "** usuarios",
            inline=True
        )

        # Comandos
        embed.add_field(
            name="📋 Comandos Usados",
            value="**" + str(self.commands_used) + "**",
            inline=True
        )

        # Actividad reciente
        embed.add_field(
            name="📊 Actividad Reciente",
            value="**" + str(total_logs) + "** eventos registrados",
            inline=True
        )

        # Protecciones
        protections = [
            "Anti-Raid", "Anti-Spam", "Anti-Flood",
            "Anti-Links", "Anti-Invite", "Anti-Phishing",
            "Anti-NSFW", "Anti-Menciones", "Anti-Bots",
            "Anti-Webhook", "Anti-RoleDelete", "Anti-MassKick",
            "Anti-MassBan", "Auto-Mod", "Auto-Ban Admin",
            "Backup Auto"
        ]
        embed.add_field(
            name="🛡️ Protecciones Activas",
            value="**" + str(len(protections)) + "** protecciones\nTodas activas automaticamente",
            inline=True
        )

        # RAM
        ram = psutil.virtual_memory().percent
        embed.add_field(
            name="💻 RAM",
            value="**" + str(ram) + "%**",
            inline=True
        )

        # Color segun estado
        if latency < 200:
            embed.color = 0x00FF00  # Verde
        elif latency < 500:
            embed.color = 0xFFFF00  # Amarillo
        else:
            embed.color = 0xFF0000  # Rojo

        # Footer
        embed.set_footer(
            text=BOT_FOOTER + " | " + BOT_NAME + " v" + BOT_VERSION,
            icon_url=self.bot.user.display_avatar.url
        )

        return embed

    def _format_uptime(self, delta):
        """Formatea el uptime"""
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(str(days) + "d")
        if hours > 0:
            parts.append(str(hours) + "h")
        if minutes > 0:
            parts.append(str(minutes) + "m")
        parts.append(str(seconds) + "s")

        return " ".join(parts)


async def setup(bot):
    await bot.add_cog(Dashboard(bot))
