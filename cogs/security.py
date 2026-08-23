"""
cogs/security.py — Motor de Seguridad v6
Anti-Raid, Anti-Spam, Anti-Flood, Anti-Links, Anti-Phishing
Anti-NSFW, Anti-Bots, Palabras Prohibidas, Detección de Alts
"""
import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
import time
import re
from datetime import datetime, timedelta

from config import (
    RAID_JOIN_THRESHOLD, RAID_TIME_WINDOW, SPAM_THRESHOLD, SPAM_TIME_WINDOW,
    MUTE_DEFAULT_DURATION, MAX_MENTIONS, MAX_CAPS_PERCENT, MIN_CAPS_LENGTH,
    MAX_EMOJI_COUNT, BANNED_WORDS, PHISHING_DOMAINS, SECURITY_ROLES,
    BLOCK_ALL_LINKS, NSFW_KEYWORDS, FLOOD_THRESHOLD, FLOOD_TIME_WINDOW,
    SUSPICIOUS_NAMES, ALT_ACCOUNT_DAYS, BOT_NAME,
    COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_ORANGE
)
from utils.embeds import (
    create_embed, raid_detected, spam_detected, link_blocked,
    phishing_detected, nsfw_detected, flood_detected, mention_spam,
    unauthorized_bot, security_status
)
from database import db


class Security(commands.Cog):
    """Motor de seguridad principal"""

    def __init__(self, bot):
        self.bot = bot
        self.join_times = defaultdict(list)
        self.msg_times = defaultdict(list)
        self.flood_tracker = defaultdict(list)
        self.raid_cooldown = {}
        self.link_pattern = re.compile(
            r'https?://[^\s]+|www\.[^\s]+|discord\.gg/[a-zA-Z0-9]+|discord\.com/invite/[a-zA-Z0-9]+',
            re.IGNORECASE
        )

    # ═══════════════════════════════════════════
    #  EVENTOS
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = await db.get_settings(guild.id) or {}
        await db.ensure_settings(guild.id)

        # Bot no autorizado
        if member.bot:
            await self._handle_bot(member)
            return

        # Anti-Raid
        if settings.get("anti_raid", True):
            await self._check_raid(member)

        # Cuenta nueva
        account_age = (datetime.utcnow() - member.created_at).days
        if account_age < ALT_ACCOUNT_DAYS:
            await self._alert_log(guild, "🔍 CUENTA NUEVA",
                f"**{member.mention}** tiene una cuenta de solo **{account_age} días** (posible alt)",
                COLOR_ORANGE)

        # Blacklist
        if await db.is_blacklisted(guild.id, member.id):
            try:
                await member.ban(reason="Auto-ban: en blacklist")
                await self._log(guild, "blacklist_ban", member.id, details="En blacklist")
            except discord.Forbidden:
                pass

        # Nombre sospechoso
        if member.name.lower() in SUSPICIOUS_NAMES or member.display_name.lower() in SUSPICIOUS_NAMES:
            await self._alert_log(guild, "🔍 NOMBRE SOSPECHOSO",
                f"**{member.mention}** tiene un nombre sospechoso: `{member.name}`",
                COLOR_ORANGE)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self._log(member.guild, "member_leave", member.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        settings = await db.get_settings(guild_id) or {}

        # Whitelist = inmune
        if await db.is_whitelisted(guild_id, user_id):
            return

        # Anti-Flood
        if settings.get("anti_spam", True):
            if await self._check_flood(message, settings):
                return

        # Anti-Spam
        if settings.get("anti_spam", True):
            if await self._check_spam(message, settings):
                return

        # Anti-Menciones
        if settings.get("auto_mod", True):
            if await self._check_mentions(message):
                return

        # Anti-Links
        if BLOCK_ALL_LINKS:
            if await self._check_links(message):
                return

        # Anti-Phishing
        if settings.get("anti_phishing", True):
            if await self._check_phishing(message):
                return

        # Anti-NSFW
        if await self._check_nsfw(message):
            return

        # Auto-Mod
        if settings.get("auto_mod", True):
            await self._check_automod(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        await self._log(message.guild, "message_delete", message.author.id,
                        details=f"Canal: {message.channel.mention}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        action = ""
        if before.channel is None and after.channel:
            action = f"Conectado a {after.channel.name}"
        elif before.channel and after.channel is None:
            action = f"Desconectado de {before.channel.name}"
        if action:
            await self._log(member.guild, "voice_state", member.id, details=action)

    # ═══════════════════════════════════════════
    #  MONITOREO DE ADMINS
    # ═══════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id and not entry.user.bot:
                    await self._alert_log(guild, "⚠️ CANAL ELIMINADO",
                        f"**{entry.user.mention}** eliminó el canal **#{channel.name}**\n`ID: {channel.id}`",
                        COLOR_RED)
                    await self._log(guild, "admin_channel_delete", entry.user.id,
                                    details=f"Canal eliminado: #{channel.name}")
                    try:
                        dm = create_embed("⚠️ ACCIÓN MONITOREADA",
                            f"Eliminaste el canal **#{channel.name}** en **{guild.name}**",
                            COLOR_RED,
                            [("📝 Canal", f"#{channel.id}", True),
                             ("🕐 Hora", f"<t:{int(datetime.utcnow().timestamp())}:F>", True)])
                        await entry.user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"Nombre: #{before.name} → #{after.name}")
        if before.topic != after.topic:
            changes.append("Tema modificado")
        if not changes:
            return

        guild = before.guild
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id and not entry.user.bot:
                    await self._alert_log(guild, "⚠️ CANAL EDITADO",
                        f"**{entry.user.mention}** editó **#{after.name}**\n" + "\n".join(changes),
                        COLOR_YELLOW)
                    try:
                        dm = create_embed("✏️ CANAL EDITADO",
                            f"Editaste **#{after.name}** en **{guild.name}**",
                            COLOR_YELLOW,
                            [("📝 Cambios", "\n".join(changes), False)])
                        await entry.user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id and not entry.user.bot:
                    await self._alert_log(guild, "🔨 BAN EJECUTADO",
                        f"**{entry.user.mention}** baneó a **{user}**\nRazón: {entry.reason or 'Sin razón'}",
                        COLOR_RED)
                    try:
                        dm = create_embed("🔨 HAS SIDO BANEADO",
                            f"Fuiste baneado de **{guild.name}**",
                            COLOR_RED,
                            [("📝 Razón", entry.reason or "Sin razón", False),
                             ("👮 Moderador", str(entry.user), True)])
                        await user.send(embed=dm)
                    except discord.Forbidden:
                        pass
                    return
        except discord.Forbidden:
            pass

    # ═══════════════════════════════════════════
    #  MOTOR DE SEGURIDAD
    # ═══════════════════════════════════════════

    async def _check_raid(self, member):
        gid = member.guild.id
        now = time.time()
        threshold = RAID_JOIN_THRESHOLD

        self.join_times[gid].append(now)
        self.join_times[gid] = [t for t in self.join_times[gid] if now - t < RAID_TIME_WINDOW]

        if len(self.join_times[gid]) >= threshold:
            if gid in self.raid_cooldown and now - self.raid_cooldown[gid] < 60:
                return
            self.raid_cooldown[gid] = now

            await self._alert_log(member.guild, "🚨 RAID DETECTADO",
                f"**{len(self.join_times[gid])}** usuarios se unieron en **{RAID_TIME_WINDOW}** segundos",
                COLOR_RED)

            recent = [
                m for m in member.guild.members
                if m.joined_at and (datetime.utcnow() - m.joined_at).total_seconds() < RAID_TIME_WINDOW
                and not m.bot
            ]
            for m in recent:
                try:
                    dm = create_embed("🚨 BAN POR RAID",
                        f"Fuiste baneado de **{member.guild.name}** por ser parte de un raid.",
                        COLOR_RED,
                        [("📝 Razón", f"Raid: {len(self.join_times[gid])} joins en {RAID_TIME_WINDOW}s", False)])
                    await m.send(embed=dm)
                except discord.Forbidden:
                    pass
                try:
                    await m.ban(reason="Anti-Raid")
                    await self._log(member.guild, "raid_ban", m.id, details="Auto-ban por raid")
                except discord.Forbidden:
                    pass

            self.join_times[gid] = []

    async def _check_spam(self, message):
        uid = message.author.id
        now = time.time()
        settings = await db.get_settings(message.guild.id) or {}
        threshold = settings.get("spam_threshold", SPAM_THRESHOLD)

        self.msg_times[uid].append(now)
        self.msg_times[uid] = [t for t in self.msg_times[uid] if now - t < SPAM_TIME_WINDOW]

        if len(self.msg_times[uid]) >= threshold:
            duration = settings.get("mute_duration", MUTE_DEFAULT_DURATION)
            until = discord.utils.utcnow() + timedelta(seconds=duration)
            try:
                await message.author.timeout(until, reason="Anti-Spam")
                await message.channel.send(embed=spam_detected(message.author, len(self.msg_times[uid])), delete_after=10)
                await self._dm(message.author, "🔇 SILENCIADO POR SPAM",
                    f"Fuiste silenciado en **{message.guild.name}** por spam.",
                    COLOR_BLUE,
                    [("📝 Razón", f"{len(self.msg_times[uid])} mensajes en {SPAM_TIME_WINDOW}s", False),
                     ("⏱️ Duración", f"{duration // 60} minutos", True)])
                await self._log(message.guild, "spam_mute", uid, details=f"{len(self.msg_times[uid])} msgs")
                self.msg_times[uid] = []
                return True
            except discord.Forbidden:
                pass
        return False

    async def _check_flood(self, message, settings):
        uid = message.author.id
        now = time.time()

        self.flood_tracker[uid].append(now)
        self.flood_tracker[uid] = [t for t in self.flood_tracker[uid] if now - t < FLOOD_TIME_WINDOW]

        if len(self.flood_tracker[uid]) >= FLOOD_THRESHOLD:
            count = len(self.flood_tracker[uid])
            await db.add_warn(message.guild.id, uid, self.bot.user.id, f"Flood: {count} msgs en {FLOOD_TIME_WINDOW}s")
            warn_count = await db.get_warn_count(message.guild.id, uid)

            try:
                until = discord.utils.utcnow() + timedelta(seconds=MUTE_DEFAULT_DURATION)
                await message.author.timeout(until, reason="Anti-Flood")
                await message.delete()
                await message.channel.send(embed=flood_detected(message.author, count, FLOOD_TIME_WINDOW), delete_after=10)
                await self._dm(message.author, "⚡ FLOOD DETECTADO",
                    f"Fuiste silenciado en **{message.guild.name}** por flood.",
                    COLOR_ORANGE,
                    [("📝 Mensajes rápidos", f"{count} en {FLOOD_TIME_WINDOW}s", False),
                     ("⚠️ Warns totales", str(warn_count), True),
                     ("🔇 Duración", f"{MUTE_DEFAULT_DURATION // 60} min", True)])
                await self._log(message.guild, "flood_mute", uid, details=f"{count} msgs en {FLOOD_TIME_WINDOW}s")
                self.flood_tracker[uid] = []
                return True
            except discord.Forbidden:
                pass
        return False

    async def _check_mentions(self, message):
        count = len(message.mentions) + len(message.role_mentions)
        if count <= MAX_MENTIONS:
            return False

        await message.delete()
        await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, f"Menciones excesivas: {count}")
        warn_count = await db.get_warn_count(message.guild.id, message.author.id)

        await message.channel.send(embed=mention_spam(message.author, count), delete_after=10)
        await self._dm(message.author, "📢 MENCIONES EXCESIVAS",
            f"Tu mensaje fue eliminado en **{message.guild.name}** por menciones excesivas.",
            COLOR_RED,
            [("📍 Canal", f"#{message.channel.name}", True),
             ("📢 Menciones", str(count), True),
             ("⚠️ Warns", str(warn_count), True),
             ("📝 Tu mensaje", message.content[:500], False)])
        await self._log(message.guild, "mention_spam", message.author.id,
                        details=f"{count} menciones en #{message.channel.name}")
        return True

    async def _check_links(self, message):
        urls = self.link_pattern.findall(message.content)
        if not urls:
            return False

        allowed = ["reglas", "rules", "links", "recursos"]
        if any(ch in message.channel.name.lower() for ch in allowed):
            return False

        try:
            await message.delete()
        except discord.Forbidden:
            return False

        await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, f"Link: {urls[0][:80]}")
        warn_count = await db.get_warn_count(message.guild.id, message.author.id)

        await message.channel.send(embed=link_blocked(message.author, urls[0], warn_count), delete_after=10)
        await self._dm(message.author, "🔗 LINK BLOQUEADO",
            f"Tu mensaje fue eliminado en **{message.guild.name}** por contener un link.",
            COLOR_RED,
            [("📍 Canal", f"#{message.channel.name}", True),
             ("🔗 Link", f"||{urls[0][:100]}||", False),
             ("⚠️ Warns", f"{warn_count}/5", True),
             ("📝 Tu mensaje", message.content[:500], False)])
        await self._log(message.guild, "link_blocked", message.author.id, details=urls[0][:100])
        return True

    async def _check_phishing(self, message):
        content = message.content.lower()
        urls = re.findall(r'https?://[^\s]+', content)

        for url in urls:
            for domain in PHISHING_DOMAINS:
                if domain.lower() in url.lower():
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass

                    await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, f"Phishing: {url[:80]}")

                    try:
                        await message.author.ban(reason=f"Phishing: {url[:80]}")
                    except discord.Forbidden:
                        pass

                    await message.channel.send(embed=phishing_detected(message.author, url), delete_after=10)
                    await self._dm(message.author, "🎣 PHISHING DETECTADO",
                        f"Fuiste baneado de **{message.guild.name}** por enviar un link de phishing.",
                        COLOR_RED,
                        [("🔗 Link malicioso", f"||{url[:100]}||", False),
                         ("📝 Tu mensaje", message.content[:500], False)])
                    await self._log(message.guild, "phishing_ban", message.author.id, details=url[:100])
                    return True
        return False

    async def _check_nsfw(self, message):
        content = message.content.lower()
        detected = False
        reason = ""

        for kw in NSFW_KEYWORDS:
            if kw in content:
                detected = True
                reason = f"Texto NSFW: '{kw}'"
                break

        if not detected:
            for att in message.attachments:
                if att.filename:
                    fn = att.filename.lower()
                    if any(x in fn for x in ["nsfw", "porn", "xxx", "nude", "hentai"]):
                        detected = True
                        reason = f"Archivo NSFW: {att.filename}"
                        break

        if not detected:
            return False

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        try:
            await message.author.ban(reason=f"NSFW: {reason}")
        except discord.Forbidden:
            try:
                until = discord.utils.utcnow() + timedelta(hours=24)
                await message.author.timeout(until, reason=f"NSFW: {reason}")
            except discord.Forbidden:
                pass

        await message.channel.send(embed=nsfw_detected(message.author), delete_after=10)
        await self._dm(message.author, "🚫 CONTENIDO NSFW",
            f"Fuiste baneado de **{message.guild.name}** por contenido NSFW.",
            COLOR_RED,
            [("📝 Razón", reason, False)])
        await self._log(message.guild, "nsfw_ban", message.author.id, details=reason)
        return True

    async def _check_automod(self, message):
        content = message.content

        # Mayúsculas excesivas
        if len(content) > MIN_CAPS_LENGTH:
            caps = sum(1 for c in content if c.isupper())
            if (caps / len(content)) * 100 > MAX_CAPS_PERCENT:
                try:
                    await message.delete()
                    await self._alert_log(message.guild, "🔠 CAPS BLOQUEADOS",
                        f"**{message.author.mention}** — exceso de mayúsculas en {message.channel.mention}",
                        COLOR_YELLOW)
                    return
                except discord.Forbidden:
                    pass

        # Palabras prohibidas
        lower = content.lower()
        for word in BANNED_WORDS:
            if word in lower:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass

                await db.add_warn(message.guild.id, message.author.id, self.bot.user.id, f"Palabra prohibida: {word}")
                warn_count = await db.get_warn_count(message.guild.id, message.author.id)

                await self._dm(message.author, "🚫 PALABRA PROHIBIDA",
                    f"Tu mensaje fue eliminado en **{message.guild.name}**.",
                    COLOR_RED,
                    [("📍 Canal", f"#{message.channel.name}", True),
                     ("⚠️ Warns", str(warn_count), True),
                     ("📝 Tu mensaje", content[:500], False)])
                await self._log(message.guild, "banned_word", message.author.id, details=f"Palabra: {word}")
                return

        # Emojis excesivos
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+", flags=re.UNICODE)
        if len(emoji_pattern.findall(content)) > MAX_EMOJI_COUNT:
            try:
                await message.delete()
                await self._alert_log(message.guild, "😀 EMOJIS BLOQUEADOS",
                    f"**{message.author.mention}** — exceso de emojis", COLOR_YELLOW)
            except discord.Forbidden:
                pass

    async def _handle_bot(self, member):
        guild = member.guild
        inviter = None
        try:
            async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    inviter = entry.user
                    break
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason="Bot no autorizado")
        except discord.Forbidden:
            pass

        await message.channel.send(embed=unauthorized_bot(member, inviter), delete_after=15)

        if inviter and not inviter.bot:
            try:
                await self._dm(inviter, "👢 EXPULSADO",
                    f"Fuiste expulsado de **{guild.name}** por invitar un bot no autorizado.",
                    COLOR_RED,
                    [("🤖 Bot baneado", str(member), True)])
                await inviter.kick(reason="Invitó bot no autorizado")
            except (discord.Forbidden, Exception):
                pass

        await self._log(guild, "unauthorized_bot", member.id,
                        inviter.id if inviter else None,
                        details=f"Bot: {member.name}")

    # ═══════════════════════════════════════════
    #  COMANDOS
    # ═══════════════════════════════════════════

    @app_commands.command(name="security", description="Ver estado de seguridad del servidor")
    async def security_cmd(self, interaction: discord.Interaction):
        settings = await db.get_settings(interaction.guild.id)
        if not settings:
            await db.ensure_settings(interaction.guild.id)
            settings = await db.get_settings(interaction.guild.id)
        total_warns = await db.get_warn_count(interaction.guild.id, 0) or 0
        await interaction.response.send_message(
            embed=security_status(interaction.guild, settings, total_warns))

    @app_commands.command(name="raid", description="Configurar anti-raid")
    @app_commands.describe(threshold="Joins para activar", window="Segundos de ventana")
    async def raid_cmd(self, interaction: discord.Interaction, threshold: int = None, window: int = None):
        if not self._has_role(interaction):
            return
        updates = {}
        if threshold: updates["raid_threshold"] = threshold
        if window: updates["raid_window"] = window
        if updates:
            await db.update_settings(interaction.guild.id, **updates)
        settings = await db.get_settings(interaction.guild.id) or {}
        await interaction.response.send_message(embed=create_embed("🚨 Anti-Raid Config",
            "Configurado correctamente", COLOR_GREEN,
            [("👥 Umbral", f"{settings.get('raid_threshold', RAID_JOIN_THRESHOLD)} joins", True),
             ("⏱️ Ventana", f"{settings.get('raid_window', RAID_TIME_WINDOW)}s", True)]))

    @app_commands.command(name="antispam", description="Configurar anti-spam")
    @app_commands.describe(threshold="Mensajes para activar", mute_duration="Duración del mute en segundos")
    async def antispam_cmd(self, interaction: discord.Interaction, threshold: int = None, mute_duration: int = None):
        if not self._has_role(interaction):
            return
        updates = {}
        if threshold: updates["spam_threshold"] = threshold
        if mute_duration: updates["mute_duration"] = mute_duration
        if updates:
            await db.update_settings(interaction.guild.id, **updates)
        settings = await db.get_settings(interaction.guild.id) or {}
        await interaction.response.send_message(embed=create_embed("🚫 Anti-Spam Config",
            "Configurado correctamente", COLOR_GREEN,
            [("💬 Umbral", f"{settings.get('spam_threshold', SPAM_THRESHOLD)} msgs", True),
             ("🔇 Mute", f"{settings.get('mute_duration', MUTE_DEFAULT_DURATION)}s", True)]))

    # ═══════════════════════════════════════════
    #  UTILIDADES
    # ═══════════════════════════════════════════

    def _has_role(self, interaction):
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

    async def _alert_log(self, guild, title, description, color):
        settings = await db.get_settings(guild.id) or {}
        ch_id = settings.get("log_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(embed=create_embed(title, description, color))
                except discord.Forbidden:
                    pass

    async def _log(self, guild, event_type, user_id=None, moderator_id=None, details=None):
        await db.add_log(guild.id, event_type, user_id, moderator_id, details)


async def setup(bot):
    await bot.add_cog(Security(bot))
