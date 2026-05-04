import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class RoleLogs(commands.Cog):
    """Logs de criação, edição e deleção de cargos"""
    
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
    
    # ═══════════════ ROLE CREATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log de cargo criado"""
        
        log_channel_id = await self.get_log_channel(role.guild.id, "role_create")
        
        if log_channel_id:
            log_channel = role.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="👔 Cargo criado",
                    description=f"Cargo **{role.name}** criado",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="📛 Nome", value=role.name, inline=True)
                embed.add_field(name="🆔 ID", value=role.id, inline=True)
                embed.add_field(name="🎨 Cor", value=str(role.color), inline=True)
                embed.add_field(name="🔢 Posição", value=role.position, inline=True)
                embed.add_field(name="👁️ Mencionável", value="Sim" if role.mentionable else "Não", inline=True)
                embed.add_field(name="📌 Exibir separado", value="Sim" if role.hoist else "Não", inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=role.guild.id,
            log_type="role_create",
            data={
                "role_name": role.name,
                "role_id": str(role.id),
                "role_color": str(role.color),
                "position": role.position,
                "mentionable": role.mentionable,
                "hoist": role.hoist,
                "permissions": role.permissions.value
            }
        )
    
    # ═══════════════ ROLE DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log de cargo deletado"""
        
        log_channel_id = await self.get_log_channel(role.guild.id, "role_delete")
        
        if log_channel_id:
            log_channel = role.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Cargo deletado",
                    description=f"Cargo **{role.name}** removido",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="📛 Nome", value=role.name, inline=True)
                embed.add_field(name="🆔 ID", value=role.id, inline=True)
                embed.add_field(name="🎨 Cor", value=str(role.color), inline=True)
                
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=role.guild.id,
            log_type="role_delete",
            data={
                "role_name": role.name,
                "role_id": str(role.id),
                "role_color": str(role.color),
                "position": role.position
            }
        )
    
    # ═══════════════ ROLE UPDATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Log de cargo editado"""
        
        log_channel_id = await self.get_log_channel(after.guild.id, "role_update")
        
        if not log_channel_id:
            return
        
        log_channel = after.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes = {}
        
        # Nome
        if before.name != after.name:
            changes["name"] = {"old": before.name, "new": after.name}
        
        # Cor
        if before.color != after.color:
            changes["color"] = {"old": str(before.color), "new": str(after.color)}
        
        # Mencionável
        if before.mentionable != after.mentionable:
            changes["mentionable"] = {"old": before.mentionable, "new": after.mentionable}
        
        # Exibir separado (hoist)
        if before.hoist != after.hoist:
            changes["hoist"] = {"old": before.hoist, "new": after.hoist}
        
        # Posição
        if before.position != after.position:
            changes["position"] = {"old": before.position, "new": after.position}
        
        # Permissões
        if before.permissions != after.permissions:
            old_perms = [perm for perm, value in before.permissions if value]
            new_perms = [perm for perm, value in after.permissions if value]
            
            added = set(new_perms) - set(old_perms)
            removed = set(old_perms) - set(new_perms)
            
            if added or removed:
                changes["permissions"] = {
                    "added": list(added),
                    "removed": list(removed)
                }
        
        if not changes:
            return
        
        # Embed
        embed = discord.Embed(
            title="✏️ Cargo editado",
            description=f"Cargo **{after.name}**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        for key, value in changes.items():
            name_map = {
                "name": "📛 Nome",
                "color": "🎨 Cor",
                "mentionable": "👁️ Mencionável",
                "hoist": "📌 Exibir separado",
                "position": "🔢 Posição",
                "permissions": "🔒 Permissões"
            }
            
            if key == "permissions":
                perms_text = ""
                if value.get("added"):
                    perms_text += f"✅ Adicionadas: {', '.join(value['added'][:5])}\n"
                if value.get("removed"):
                    perms_text += f"❌ Removidas: {', '.join(value['removed'][:5])}"
                embed.add_field(name=name_map[key], value=perms_text[:1024] or "-", inline=False)
            else:
                embed.add_field(
                    name=name_map.get(key, key),
                    value=f"❌ {value['old']}\n✅ {value['new']}",
                    inline=True
                )
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=after.guild.id,
            log_type="role_update",
            data={
                "role_name": after.name,
                "role_id": str(after.id),
                "changes": {k: v for k, v in changes.items() if k != "permissions"},
                "permission_changes": changes.get("permissions", {})
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleLogs(bot))