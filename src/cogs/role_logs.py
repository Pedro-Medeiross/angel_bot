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
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.log_api = log_api
        self._position_queue: dict = {}
        self._position_task: dict = {}
    
    async def _get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/log-channel/{log_type}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("channel_id")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao consultar API: {e}")
        return None
    
    def _build_role_embed(self, title: str, description: str, color: discord.Color,
                          role: discord.Role = None) -> discord.Embed:
        """Cria embed base para logs de cargo"""
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        if role:
            embed.add_field(name="📛 Nome", value=role.name, inline=True)
            embed.add_field(name="🆔 ID", value=role.id, inline=True)
            embed.add_field(name="🎨 Cor", value=str(role.color), inline=True)
        return embed
    
    def _build_role_data(self, role: discord.Role) -> dict:
        """Dados base do cargo para API"""
        return {
            "role_name": role.name,
            "role_id": str(role.id),
            "role_color": str(role.color),
            "position": role.position,
        }
    
    def _build_member_role_embed(self, member: discord.Member, title: str, description: str,
                                  color: discord.Color) -> discord.Embed:
        """Cria embed para logs de cargo de membro"""
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} | @{member.name}")
        embed.add_field(name="👤 Membro", value=member.mention, inline=True)
        return embed
    
    def _build_member_data(self, member: discord.Member) -> dict:
        """Dados base do membro para API"""
        return {
            "user_name": member.name,
            "display_name": member.display_name,
            "user_avatar": str(member.display_avatar.url),
        }
    
    # ═══════════════ ROLE CREATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel_id = await self._get_log_channel(role.guild.id, "role_create")
        
        if log_channel_id:
            log_channel = role.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_role_embed("👔 Cargo criado", f"Cargo **{role.name}** criado", discord.Color.green(), role)
                embed.add_field(name="🔢 Posição", value=role.position, inline=True)
                embed.add_field(name="👁️ Mencionável", value="Sim" if role.mentionable else "Não", inline=True)
                embed.add_field(name="📌 Exibir separado", value="Sim" if role.hoist else "Não", inline=True)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=role.guild.id, log_type="role_create", data={
            **self._build_role_data(role),
            "mentionable": role.mentionable, "hoist": role.hoist, "permissions": role.permissions.value
        })
    
    # ═══════════════ ROLE DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel_id = await self._get_log_channel(role.guild.id, "role_delete")
        
        if log_channel_id:
            log_channel = role.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_role_embed("🗑️ Cargo deletado", f"Cargo **{role.name}** removido", discord.Color.red(), role)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=role.guild.id, log_type="role_delete", data=self._build_role_data(role))
    
    # ═══════════════ ROLE UPDATE ═══════════════
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.position != after.position and before.name == after.name and before.color == after.color:
            guild_id = after.guild.id
            self._position_queue.setdefault(guild_id, {})[after.id] = (before.position, after.position, after.name)
            
            if guild_id in self._position_task:
                self._position_task[guild_id].cancel()
            self._position_task[guild_id] = asyncio.create_task(self._flush_position_changes(after.guild))
            return
        
        await self._log_single_role_update(before, after)
    
    async def _flush_position_changes(self, guild: discord.Guild):
        await asyncio.sleep(1)
        
        queue = self._position_queue.pop(guild.id, {})
        if not queue:
            return
        
        log_channel_id = await self._get_log_channel(guild.id, "role_update")
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        changes_list = [f"**{name}**: {old} → {new}" for _, (old, new, name) in queue.items()]
        
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
        
        await self.log_api.send_log(guild_id=guild.id, log_type="role_update", data={
            "type": "position_bulk",
            "changes": [{"role_id": str(rid), "role_name": name, "old_position": old, "new_position": new}
                        for rid, (old, new, name) in queue.items()]
        })
    
    async def _log_single_role_update(self, before: discord.Role, after: discord.Role):
        log_channel_id = await self._get_log_channel(after.guild.id, "role_update")
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
            old_perms = {p for p, v in before.permissions if v}
            new_perms = {p for p, v in after.permissions if v}
            added = new_perms - old_perms
            removed = old_perms - new_perms
            if added or removed:
                changes["permissions"] = {"added": list(added), "removed": list(removed)}
        
        if not changes:
            return
        
        embed = discord.Embed(
            title="✏️ Cargo editado", description=f"Cargo **{after.name}**",
            color=discord.Color.orange(), timestamp=discord.utils.utcnow()
        )
        
        name_map = {
            "name": "📛 Nome", "color": "🎨 Cor", "mentionable": "👁️ Mencionável",
            "hoist": "📌 Exibir separado", "permissions": "🔒 Permissões"
        }
        
        for key, value in changes.items():
            if key == "permissions":
                perms_text = ""
                if value.get("added"):
                    perms_text += f"✅ Adicionadas: {', '.join(value['added'][:5])}\n"
                if value.get("removed"):
                    perms_text += f"❌ Removidas: {', '.join(value['removed'][:5])}"
                embed.add_field(name=name_map[key], value=perms_text[:1024] or "-", inline=False)
            else:
                embed.add_field(name=name_map.get(key, key), value=f"❌ {value['old']}\n✅ {value['new']}", inline=True)
        
        await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=after.guild.id, log_type="role_update", data={
            "role_name": after.name, "role_id": str(after.id),
            "changes": {k: v for k, v in changes.items() if k != "permissions"},
            "permission_changes": changes.get("permissions", {})
        })
    
    # ═══════════════ MEMBER ROLE ADD/REMOVE ═══════════════
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        for role in added_roles:
            await self._log_member_role(after, role, "member_role_add", "👔 Cargo adicionado",
                                        f"Cargo adicionado a {after.mention}", discord.Color.green(), role.mention)
        
        for role in removed_roles:
            await self._log_member_role(after, role, "member_role_remove", "👔 Cargo removido",
                                        f"Cargo removido de {after.mention}", discord.Color.red(), role.name)
    
    async def _log_member_role(self, member: discord.Member, role: discord.Role, log_type: str,
                                title: str, description: str, color: discord.Color, role_display: str):
        log_channel_id = await self._get_log_channel(member.guild.id, log_type)
        
        if log_channel_id:
            log_channel = member.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_member_role_embed(member, title, description, color)
                embed.add_field(name="👔 Cargo", value=role_display, inline=True)
                embed.add_field(name="🆔 Cargo ID", value=role.id, inline=True)
                await log_channel.send(embed=embed)
        
        await self.log_api.send_log(guild_id=member.guild.id, log_type=log_type, target_id=member.id, data={
            **self._build_member_data(member),
            "role_name": role.name, "role_id": str(role.id), "role_color": str(role.color)
        })

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleLogs(bot))