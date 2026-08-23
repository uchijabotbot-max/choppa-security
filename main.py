"""
main.py — Bot de Seguridad Avanzado
by choppa
"""
import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database.db import init_db

# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("security_bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("SecurityBot")

# ─────────────────────────────────────────────────────────────
#  Cargar variables de entorno
# ─────────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.critical("❌ No se encontró DISCORD_TOKEN en .env")
    raise SystemExit(1)

# ─────────────────────────────────────────────────────────────
#  Intents
# ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.voice_states = True

# ─────────────────────────────────────────────────────────────
#  Bot
# ─────────────────────────────────────────────────────────────
class SecurityBot(commands.Bot):
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
            "cogs.logging",
            "cogs.verification",
            "cogs.info",
            "cogs.nuclear",
            "cogs.audit",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog cargado: {cog}")
            except Exception as e:
                logger.error(f"❌ Error cargando {cog}: {e}", exc_info=True)

        # Sincronizar slash commands
        logger.info("🔄 Sincronizando slash commands...")
        synced = await self.tree.sync()
        logger.info(f"✅ {len(synced)} slash commands sincronizados.")

    async def on_ready(self):
        logger.info("")
        logger.info("  ╔══════════════════════════════════════╗")
        logger.info("  ║   Bot de Seguridad Conectado         ║")
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

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"📥 Unido al servidor: {guild.name} ({guild.id}) — {guild.member_count} miembros")

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"📤 Salí del servidor: {guild.name} ({guild.id})")

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handler global de errores"""
        import utils.embeds as embeds
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                embed=embeds.create_embed(
                    "Cooldown",
                    f"Espera **{error.retry_after:.1f}s** antes de volver a usar este comando.",
                    color=0xFEE75C
                ),
                ephemeral=True
            )
        elif isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=embeds.create_embed(
                    "Sin permisos",
                    "No tienes los permisos necesarios para este comando.",
                    color=0xED4245
                ),
                ephemeral=True
            )
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                embed=embeds.create_embed(
                    "Bot sin permisos",
                    f"Me faltan permisos: `{', '.join(error.missing_permissions)}`",
                    color=0xED4245
                ),
                ephemeral=True
            )
        else:
            logger.error(f"Error en comando {interaction.command}: {error}", exc_info=True)
            try:
                await interaction.response.send_message(
                    embed=embeds.create_embed(
                        "Error inesperado",
                        "Ocurrió un error. Por favor intenta de nuevo.",
                        color=0xED4245
                    ),
                    ephemeral=True
                )
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
#  Entrada principal
# ─────────────────────────────────────────────────────────────
async def main():
    bot = SecurityBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
