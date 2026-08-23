"""
main.py — Choppa Security v6.0
Bot de seguridad más avanzado para Discord
by choppa
"""
import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database.db import init_db

# ── Logging ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ChoppaSecurity")

# ── Token ───────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.critical("❌ DISCORD_TOKEN no encontrado en variables de entorno")
    raise SystemExit(1)

# ── Intents ─────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.voice_states = True


# ── Bot ─────────────────────────────────────────
class ChoppaSecurity(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            case_insensitive=True
        )

    async def setup_hook(self):
        """Cargar cogs y sincronizar slash commands"""
        logger.info("⚙️ Inicializando base de datos...")
        await init_db()

        cogs = [
            "cogs.security",
            "cogs.moderation",
            "cogs.info",
        ]

        loaded = 0
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cargado: {cog}")
                loaded += 1
            except Exception as e:
                logger.error(f"❌ Error cargando {cog}: {e}")

        logger.info(f"🔄 Sincronizando slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} comandos sincronizados")
        except Exception as e:
            logger.error(f"❌ Error sincronizando: {e}")

        logger.info(f"✅ {loaded}/{len(cogs)} cogs cargados correctamente")

    async def on_ready(self):
        logger.info("")
        logger.info("  ╔══════════════════════════════════════╗")
        logger.info("  ║   🛡️  Choppa Security v6.0           ║")
        logger.info(f"  ║   Nombre: {self.user.name:<27}║")
        logger.info(f"  ║   ID: {self.user.id:<32}║")
        logger.info(f"  ║   Servidores: {len(self.guilds):<23}║")
        logger.info("  ╚══════════════════════════════════════╝")
        logger.info("")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servidor(es) 🛡️"
            ),
            status=discord.Status.online
        )

    async def on_guild_join(self, guild):
        logger.info(f"📥 Unido a: {guild.name} ({guild.member_count} miembros)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servidor(es) 🛡️"
            )
        )

        # Activar TODAS las protecciones automaticamente
        from database.db import ensure_settings
        await ensure_settings(guild.id)

        # Buscar canal para enviar bienvenida
        channel = None
        for ch in guild.text_channels:
            if ch.name in ["general", "chat", "texto", "welcome", "bienvenida"]:
                channel = ch
                break
        if not channel:
            channel = guild.system_channel
        if not channel:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break

        if channel:
            from utils.embeds import create_embed
            embed = create_embed(
                "🛡️ Choppa Security Activado",
                "**Todas las protecciones estan activas automaticamente**",
                0x00FF00,
                fields=[
                    ("Protecciones Activas", "\n".join([
                        "✅ Anti-Raid (auto-ban)",
                        "✅ Anti-Spam (auto-mute)",
                        "✅ Anti-Flood (auto-mute)",
                        "✅ Anti-Links (auto-delete)",
                        "✅ Anti-Phishing (auto-ban)",
                        "✅ Anti-NSFW (auto-ban)",
                        "✅ Anti-Menciones (auto-delete)",
                        "✅ Anti-Bots (auto-ban)",
                        "✅ Auto-Mod (palabras, caps, emojis)",
                        "✅ Anti-Alt Accounts (alerta)",
                        "✅ Anti-Webhook (alerta)",
                        "✅ Anti-Roles Peligrosos (auto-delete)",
                        "✅ Auto-Ban Admin (borra canal)",
                        "✅ Auto-Ban Admin (modifica permisos)",
                    ]), False),
                    ("Comandos", "`/whitelist @user` - Inmune a todo\n`/blacklist @user` - Auto-ban\n`/security` - Estado\n`/help` - Todos los comandos", False),
                    ("Owner", "<@1331303237315461163>", True),
                ]
            )
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    async def on_guild_remove(self, guild):
        logger.info(f"📤 Salí de: {guild.name}")

    async def on_app_command_error(self, interaction, error):
        """Handler global de errores"""
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⏳ Cooldown",
                    description=f"Espera **{error.retry_after:.1f}s**",
                    color=0xFEE75C
                ), ephemeral=True)
        elif isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Sin permisos",
                    description="No tienes permisos para esto.",
                    color=0xFF0000
                ), ephemeral=True)
        else:
            logger.error(f"Error en comando: {error}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="Ocurrió un error. Intenta de nuevo.",
                            color=0xFF0000
                        ), ephemeral=True)
            except Exception:
                pass


# ── Entry Point ─────────────────────────────────
async def main():
    bot = ChoppaSecurity()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
