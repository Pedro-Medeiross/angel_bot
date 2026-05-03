import discord
from discord.ext import commands
import aiohttp
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
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log de mudanças no membro (nickname, roles, timeout)"""
        
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
        
        # Timeout
        if before.timed_out != after.timed_out:
            log_channel_id = await self.get_log_channel(after.guild.id, "member_timeout")
            
            if after.timed_out:
                # Timeout aplicado
                timeout_until = after.communication_disabled_until
                
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔇 Membro silenciado (timeout)",
                            description=f"{after.mention} foi silenciado",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id}")
                        
                        if timeout_until:
                            duration = timeout_until - discord.utils.utcnow()
                            minutes = int(duration.total_seconds() // 60)
                            embed.add_field(
                                name="⏰ Expira em",
                                value=f"{discord.utils.format_dt(timeout_until, 'R')} ({minutes} min)",
                                inline=False
                            )
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    user_id=None,  # Não sabemos quem aplicou
                    target_id=after.id,
                    data={
                        "target_name": str(after),
                        "action": "applied",
                        "expires_at": timeout_until.isoformat() if timeout_until else None
                    }
                )
            else:
                # Timeout removido
                if log_channel_id:
                    log_channel = after.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔊 Membro des-silenciado",
                            description=f"{after.mention} não está mais em timeout",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                        embed.set_footer(text=f"ID: {after.id}")
                        
                        await log_channel.send(embed=embed)
                
                await self.log_api.send_log(
                    guild_id=after.guild.id,
                    log_type="member_timeout",
                    user_id=None,
                    target_id=after.id,
                    data={
                        "target_name": str(after),
                        "action": "removed"
                    }
                )
    
    # ═══════════════ BAN / UNBAN ═══════════════
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Log de membro banido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_ban")
        
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
                
                embed.add_field(name="👤 Usuário", value=f"{user.mention}\n{user.name}", inline=True)
                embed.add_field(name="🆔 ID", value=str(user.id), inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_ban",
            target_id=user.id,
            data={
                "target_name": str(user),
                "target_avatar": str(user.display_avatar.url)
            }
        )
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log de membro desbanido"""
        
        log_channel_id = await self.get_log_channel(guild.id, "member_unban")
        
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
                embed.add_field(name="🆔 ID", value=str(user.id), inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="member_unban",
            target_id=user.id,
            data={
                "target_name": str(user),
                "target_avatar": str(user.display_avatar.url)
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogs(bot))