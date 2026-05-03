import discord
from discord.ext import commands, tasks
import aiohttp
from datetime import datetime, timezone, timedelta
from src.core.config import config
from src.utils.log_api import log_api

class MemberLogs(commands.Cog):
    """Logs de eventos de membro"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.log_api = log_api
        self.last_audit_check = datetime.now(timezone.utc)
        self.check_timeouts.start()
    
    def cog_unload(self):
        self.check_timeouts.cancel()
    
    async def get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/log-channel/{log_type}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("channel_id")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao consultar API: {e}")
        return None
    
    async def get_moderator(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> str | None:
        """Busca o moderador no audit log"""
        try:
            async for entry in guild.audit_logs(limit=3, action=action):
                if entry.target and entry.target.id == target_id:
                    return str(entry.user)
        except discord.Forbidden:
            pass
        return None
    
    # ═══════════════ AUDIT LOG POLLING (TIMEOUT MANUAL) ═══════════════
    
    @tasks.loop(seconds=10)
    async def check_timeouts(self):
        """Verifica audit log por timeouts aplicados manualmente"""
        for guild in self.bot.guilds:
            if not guild.me.guild_permissions.view_audit_log:
                continue
            
            log_channel_id = await self.get_log_channel(guild.id, "member_timeout")
            if not log_channel_id:
                continue
            
            try:
                async for entry in guild.audit_logs(
                    limit=5,
                    after=self.last_audit_check,
                    action=discord.AuditLogAction.member_update
                ):
                    changes = getattr(entry, 'changes', None)
                    if not changes:
                        continue
                    
                    after_changes = changes.after if hasattr(changes, 'after') else changes.get('after', {})
                    timed_out_until = after_changes.get('communication_disabled_until') if isinstance(after_changes, dict) else None
                    
                    if timed_out_until:
                        target = entry.target
                        moderator = entry.user
                        
                        if target:
                            log_channel = guild.get_channel(log_channel_id)
                            if log_channel:
                                embed = discord.Embed(
                                    title="🔇 Membro silenciado (timeout)",
                                    color=discord.Color.red(),
                                    timestamp=discord.utils.utcnow()
                                )
                                embed.set_author(name=str(target), icon_url=target.display_avatar.url)
                                embed.set_footer(text=f"ID: {target.id}")
                                embed.add_field(name="👤 Membro", value=target.mention, inline=True)
                                if moderator:
                                    embed.add_field(name="🛡️ Moderador", value=str(moderator), inline=True)
                                
                                if timed_out_until:
                                    embed.add_field(
                                        name="⏰ Expira",
                                        value=discord.utils.format_dt(timed_out_until, 'R'),
                                        inline=False
                                    )
                                
                                await log_channel.send(embed=embed)
                            
                            await self.log_api.send_log(
                                guild_id=guild.id,
                                log_type="member_timeout",
                                user_id=moderator.id if moderator else None,
                                target_id=target.id,
                                data={
                                    "target_name": str(target),
                                    "moderator_name": str(moderator) if moderator else "Unknown",
                                    "action": "applied",
                                    "expires_at": timed_out_until.isoformat() if timed_out_until else None
                                }
                            )
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"❌ Erro check_timeouts {guild.name}: {e}")
        
        self.last_audit_check = datetime.now(timezone.utc) - timedelta(seconds=5)
    
    @check_timeouts.before_loop
    async def before_check_timeouts(self):
        await self.bot.wait_until_ready()
    
    # ═══════════════ MEMBER UPDATE ═══════════════
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log de mudanças no membro (nickname, roles, timeout via API)"""
        
        # Nickname
        if before.nick != after.nick:
            log_channel_id = await self.get_log_channel(after.guild.id, "member_nickname")
            
            if log_channel_id:
                log_channel = after.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="📝 Apelido alterado",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                    embed.set_footer(text=f"ID: {after.id}")
                    
                    old_nick = before.nick or str(before)
                    new_nick = after.nick or str(after)
                    
                    embed.add_field(name="❌ Antes", value=old_nick, inline=True)
                    embed.add_field(name="✅ Depois", value=new_nick, inline=True)
                    embed.description = f"{after.mention} alterou o apelido"
                    
                    await log_channel.send(embed=embed)
            
            await self.log_api.send_log(
                guild_id=after.guild.id,
                log_type="member_nickname",
                user_id=after.id,
                data={
                    "user_name": str(after),
                    "old_nickname": before.nick or str(before),
                    "new_nickname": after.nick or str(after)
                }
            )
        
        # Timeout (via bot/API)
        if before.timed_out != after.timed_out:
            log_channel_id = await self.get_log_channel(after.guild.id, "member_timeout")
            
            moderator = await self.get_moderator(
                after.guild,
                after.id,
                discord.AuditLogAction.member_update
            )
            
            if after.timed_out:
                timeout_until = after.communication_disabled_until
                
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 Membro silenciado (timeout)",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id}")
                        
                        embed.add_field(name="👤 Membro", value=after.mention, inline=True)
                        if moderator:
                            embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                        
                        if timeout_until:
                            embed.add_field(
                                name="⏰ Expira",
                                value=discord.utils.format_dt(timeout_until, 'R'),
                                inline=False
                            )
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    user_id=None,
                    target_id=after.id,
                    data={
                        "target_name": str(after),
                        "moderator_name": moderator,
                        "action": "applied",
                        "expires_at": timeout_until.isoformat() if timeout_until else None
                    }
                )
            else:
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔊 Membro des-silenciado",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id}")
                        
                        embed.add_field(name="👤 Membro", value=after.mention, inline=True)
                        if moderator:
                            embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    user_id=None,
                    target_id=after.id,
                    data={
                        "target_name": str(after),
                        "moderator_name": moderator,
                        "action": "removed"
                    }
                )
    
    # ═══════════════ BAN / UNBAN ═══════════════
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Log de membro banido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_ban")
        
        moderator = None
        reason = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
                if entry.target and entry.target.id == user.id:
                    moderator = str(entry.user)
                    reason = entry.reason or "Nenhuma razão informada"
                    break
        except discord.Forbidden:
            pass
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🔨 Membro banido",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=str(user), icon_url=user.display_avatar.url)
                embed.set_footer(text=f"ID: {user.id}")
                
                embed.add_field(name="👤 Usuário", value=f"{user.name}", inline=True)
                if moderator:
                    embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                if reason:
                    embed.add_field(name="📝 Motivo", value=reason, inline=False)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_ban",
            target_id=user.id,
            data={
                "target_name": str(user),
                "target_avatar": str(user.display_avatar.url),
                "moderator_name": moderator,
                "reason": reason
            }
        )
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log de membro desbanido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_unban")
        
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.unban):
                if entry.target and entry.target.id == user.id:
                    moderator = str(entry.user)
                    break
        except discord.Forbidden:
            pass
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🔓 Membro desbanido",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=str(user), icon_url=user.display_avatar.url)
                embed.set_footer(text=f"ID: {user.id}")
                
                embed.add_field(name="👤 Usuário", value=f"{user.name}", inline=True)
                if moderator:
                    embed.add_field(name="🛡️ Moderador", value=moderator, inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_unban",
            target_id=user.id,
            data={
                "target_name": str(user),
                "target_avatar": str(user.display_avatar.url),
                "moderator_name": moderator
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogs(bot))