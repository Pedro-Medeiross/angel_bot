import discord
from discord.ext import commands
import asyncio
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
        self._position_queue = {}
        self._position_task = {}
    
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
        
        # Se mudou só a posição, agrupa
        if before.position != after.position and before.name == after.name and before.color == after.color:
            guild_id = after.guild.id
            
            if guild_id not in self._position_queue:
                self._position_queue[guild_id] = {}
            
            self._position_queue[guild_id][after.id] = (before.position, after.position, after.name)
            
            if guild_id in self._position_task:
                self._position_task[guild_id].cancel()
            
            self._position_task[guild_id] = asyncio.create_task(
                self._flush_position_changes(after.guild)
            )
            return
        
        # Mudanças normais (nome, cor, permissões)
        await self._log_single_role_update(before, after)
    
    async def _flush_position_changes(self, guild: discord.Guild):
        """Envia mudanças de posição agrupadas após 1 segundo"""
        await asyncio.sleep(1)
        
        queue = self._position_queue.pop(guild.id, {})
        if not queue:
            return
        
        log_channel_id = await self.get_log_channel(guild.id, "role_update")
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes_list = []
        for role_id, (old_pos, new_pos, role_name) in queue.items():
            changes_list.append(f"**{role_name}**: {old_pos} → {new_pos}")
        
        embed = discord.Embed(
            title="🔢 Posições de cargos atualizadas",
            description=f"{len(changes_list)} cargo(s) reordenado(s)",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        chunk = ""
        for line in changes_list:
            if len(chunk) + len(line) > 1024:
                embed.add_field(name="📋 Mudanças", value=chunk, inline=False)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            embed.add_field(name="📋 Mudanças", value=chunk, inline=False)
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="role_update",
            data={
                "type": "position_bulk",
                "changes": [
                    {
                        "role_id": str(role_id),
                        "role_name": role_name,
                        "old_position": old_pos,
                        "new_position": new_pos
                    }
                    for role_id, (old_pos, new_pos, role_name) in queue.items()
                ]
            }
        )
    
    async def _log_single_role_update(self, before: discord.Role, after: discord.Role):
        """Log de cargo editado (mudanças não-posição)"""
        
        log_channel_id = await self.get_log_channel(after.guild.id, "role_update")
        
        if not log_channel_id:
            return
        
        log_channel = after.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes = {}
        
        if before.name != after.name:
            changes["name"] = {"old": before.name, "new": after.name}
        
        if before.color != after.color:
            changes["color"] = {"old": str(before.color), "new": str(after.color)}
        
        if before.mentionable != after.mentionable:
            changes["mentionable"] = {"old": before.mentionable, "new": after.mentionable}
        
        if before.hoist != after.hoist:
            changes["hoist"] = {"old": before.hoist, "new": after.hoist}
        
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