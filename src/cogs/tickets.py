import discord
import asyncio
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
import aiohttp
from typing import Optional
import logging
from src.core.config import config

logger = logging.getLogger(__name__)

# ═══════════════ VIEWS ═══════════════

class TicketView(View):
    """View com botão para abrir ticket"""
    
    def __init__(self, panel_id: str, label: str, color: str):
        super().__init__(timeout=None)
        
        style_map = {
            "blue": discord.ButtonStyle.primary,
            "green": discord.ButtonStyle.success,
            "red": discord.ButtonStyle.danger,
            "gray": discord.ButtonStyle.secondary,
            "grey": discord.ButtonStyle.secondary,
        }
        style = style_map.get(color.lower(), discord.ButtonStyle.primary)
        
        self.add_item(Button(
            label=label,
            style=style,
            custom_id=f"ticket_open_{panel_id}",
            emoji="🎫"
        ))

class TicketControlView(View):
    def __init__(self, ticket_id: str, chat_locked: bool = True, claimed: bool = False):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        
        if not claimed:
            # Pré-claim: Liberar/Bloquear + Atender + Fechar
            if chat_locked:
                self.add_item(Button(label="Liberar Chat", style=discord.ButtonStyle.primary, custom_id=f"ticket_unlock_{ticket_id}", emoji="🔓", row=0))
            else:
                self.add_item(Button(label="Bloquear Chat", style=discord.ButtonStyle.secondary, custom_id=f"ticket_lock_{ticket_id}", emoji="🔒", row=0))
            self.add_item(Button(label="Atender", style=discord.ButtonStyle.success, custom_id=f"ticket_claim_{ticket_id}", emoji="👤", row=0))
            self.add_item(Button(label="Fechar", style=discord.ButtonStyle.danger, custom_id=f"ticket_close_{ticket_id}", emoji="🔒", row=0))
        else:
            # Pós-claim: Add, Remove, Transferir, Prioridade, Lock/Unlock, Fechar
            if chat_locked:
                self.add_item(Button(label="Liberar", style=discord.ButtonStyle.primary, custom_id=f"ticket_unlock_{ticket_id}", emoji="🔓", row=0))
            else:
                self.add_item(Button(label="Bloquear", style=discord.ButtonStyle.secondary, custom_id=f"ticket_lock_{ticket_id}", emoji="🔒", row=0))
            self.add_item(Button(label="Prioridade", style=discord.ButtonStyle.primary, custom_id=f"ticket_priority_{ticket_id}", emoji="⚠️", row=0))
            self.add_item(Button(label="Transferir", style=discord.ButtonStyle.primary, custom_id=f"ticket_transfer_{ticket_id}", emoji="🔄", row=0))
            self.add_item(Button(label="Add Membro", style=discord.ButtonStyle.success, custom_id=f"ticket_add_{ticket_id}", emoji="➕", row=1))
            self.add_item(Button(label="Add Cargo", style=discord.ButtonStyle.success, custom_id=f"ticket_addrole_{ticket_id}", emoji="👔", row=1))
            self.add_item(Button(label="Remover Membro", style=discord.ButtonStyle.danger, custom_id=f"ticket_remove_{ticket_id}", emoji="➖", row=2))
            self.add_item(Button(label="Remover Cargo", style=discord.ButtonStyle.danger, custom_id=f"ticket_removerole_{ticket_id}", emoji="👔", row=2))
            self.add_item(Button(label="Fechar", style=discord.ButtonStyle.danger, custom_id=f"ticket_close_{ticket_id}", emoji="🔒", row=3))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("ticket_close_"):
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        cog = interaction.client.get_cog("Tickets")
        if cog:
            staff_roles = await cog._get_staff_roles(interaction.guild.id)
            for sr in staff_roles:
                role = interaction.guild.get_role(int(sr["role_id"]))
                if role and role in interaction.user.roles:
                    return True
        await interaction.response.send_message("❌ Apenas staff pode usar este botão.", ephemeral=True)
        return False
    
class AddMemberView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.ticket_id = ticket_id
        self.cog = cog
        self.add_item(UserSelectCustom(ticket_id, cog))

class UserSelectCustom(discord.ui.UserSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um usuário para adicionar...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if isinstance(member, discord.Member):
            await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"✅ {member.mention} adicionado ao ticket.", ephemeral=True)
            # Avisa no chat
            embed = discord.Embed(
                title="➕ Membro Adicionado",
                description=f"{member.mention} foi adicionado ao ticket por {interaction.user.mention}.",
                color=discord.Color.green()
            )
            await interaction.channel.send(embed=embed)
        else:
            await interaction.response.send_message("❌ Usuário não encontrado no servidor.", ephemeral=True)

class RemoveMemberView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(RemoveUserSelect(ticket_id, cog))

class RemoveUserSelect(discord.ui.UserSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um usuário para remover...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        
        # Verifica se o membro está no canal
        overwrite = interaction.channel.overwrites_for(member)
        if overwrite.is_empty() or not overwrite.read_messages:
            await interaction.response.send_message("❌ Este usuário não está no ticket.", ephemeral=True)
            return
        
        if member.guild_permissions.administrator:
            await interaction.response.send_message("❌ Não pode remover administrador.", ephemeral=True)
            return
        
        if isinstance(member, discord.Member):
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message(f"✅ {member.mention} removido do ticket.", ephemeral=True)
            # Avisa no chat
            embed = discord.Embed(
                title="➖ Membro Removido",
                description=f"{member.mention} foi removido do ticket por {interaction.user.mention}.",
                color=discord.Color.orange()
            )
            await interaction.channel.send(embed=embed)
            
class AddRoleSelect(discord.ui.RoleSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um cargo para adicionar...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        if role.permissions.administrator:
            await interaction.response.send_message("❌ Não pode adicionar cargo de administrador.", ephemeral=True)
            return
        
        await interaction.channel.set_permissions(role, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ Cargo {role.mention} adicionado ao ticket.", ephemeral=True)
        
        embed = discord.Embed(
            title="➕ Cargo Adicionado",
            description=f"Cargo {role.mention} foi adicionado ao ticket por {interaction.user.mention}.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed)

class AddRoleView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(AddRoleSelect(ticket_id, cog))

class RemoveRoleSelect(discord.ui.RoleSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um cargo para remover...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        
        # Verifica se o cargo está no canal
        overwrite = interaction.channel.overwrites_for(role)
        if overwrite.is_empty() or not overwrite.read_messages:
            await interaction.response.send_message("❌ Este cargo não está no ticket.", ephemeral=True)
            return
        
        await interaction.channel.set_permissions(role, overwrite=None)
        await interaction.response.send_message(f"✅ Cargo {role.mention} removido do ticket.", ephemeral=True)
        
        embed = discord.Embed(
            title="➖ Cargo Removido",
            description=f"Cargo {role.mention} foi removido do ticket por {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=embed)

class RemoveRoleView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(RemoveRoleSelect(ticket_id, cog))
            
class TransferSelectView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(StaffSelect(ticket_id, cog))

class StaffSelect(discord.ui.UserSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um staff para transferir...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return
        
        # Verifica se é staff
        staff_roles = await self.cog._get_staff_roles(interaction.guild.id)
        is_staff = member.guild_permissions.administrator
        if not is_staff:
            for role in member.roles:
                if role.id in [int(sr["role_id"]) for sr in staff_roles]:
                    is_staff = True
                    break
        
        if not is_staff:
            await interaction.response.send_message("❌ O usuário não é staff.", ephemeral=True)
            return
        
        await self.cog._api_post(
            f"/guilds/{interaction.guild.id}/tickets/{self.ticket_id}/bot/transfer",
            {"to_staff_id": str(member.id)}
        )
        await interaction.response.send_message(f"✅ Ticket transferido para {member.mention}.", ephemeral=True)
        # Avisa no chat
        embed = discord.Embed(
            title="🔄 Ticket Transferido",
            description=f"Ticket transferido para {member.mention} por {interaction.user.mention}.",
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed)

class PrioritySelect(discord.ui.Select):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        
        options = [
            discord.SelectOption(label="🔴 Urgente", value="urgent", emoji="🔴"),
            discord.SelectOption(label="🟠 Alta", value="high", emoji="🟠"),
            discord.SelectOption(label="🟡 Média", value="medium", emoji="🟡"),
            discord.SelectOption(label="🟢 Baixa", value="low", emoji="🟢"),
        ]
        super().__init__(placeholder="Selecione a nova prioridade...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        priority = self.values[0]
        await self.cog._api_put(
            f"/guilds/{interaction.guild.id}/tickets/{self.ticket_id}/bot/priority",
            {"priority": priority}
        )
        
        # Reordena o canal
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        new_priority_level = priority_order.get(priority, 2)
        channel = interaction.channel
        if channel.category:
            await self.cog._reorder_category(channel.category)
        
        await interaction.response.send_message(f"✅ Prioridade alterada para **{priority.upper()}**", ephemeral=True)

class PriorityView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=60)
        self.add_item(PrioritySelect(ticket_id, cog))
        
class CloseTicketModal(Modal):
    """Modal pedindo motivo do fechamento"""
    
    def __init__(self, ticket_id: str, cog):
        super().__init__(title="Fechar Ticket")
        self.ticket_id = ticket_id
        self.cog = cog
        
        self.reason = TextInput(
            label="Mensagem de resolução",
            placeholder="Descreva o que foi resolvido...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Determina o role baseado em como chegou aqui
        await interaction.response.defer()
        ticket_info = await self.cog._get_ticket_info(interaction.guild.id, self.ticket_id)
        role = "owner" if ticket_info and str(interaction.user.id) == str(ticket_info.get("user_id")) else "claimed"
        await self.cog._close_ticket(interaction, self.ticket_id, self.reason.value, role)

class ConfirmCloseView(View):
    """View de confirmação para o usuário fechar o próprio ticket"""
    
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.cog = cog
        
        self.add_item(Button(
            label="Confirmar fechamento",
            style=discord.ButtonStyle.danger,
            custom_id=f"confirm_close_{ticket_id}",
            emoji="✅"
        ))
        self.add_item(Button(
            label="Cancelar",
            style=discord.ButtonStyle.secondary,
            custom_id=f"cancel_close_{ticket_id}",
            emoji="❌"
        ))
    
    async def on_timeout(self):
        if hasattr(self, 'message') and self.message:
            await self.message.edit(content="⏰ Tempo esgotado.", view=None)
            
# ═══════════════ CATEGORIA ═══════════════

class CategorySelect(discord.ui.Select):
    """Dropdown para escolher categoria"""
    
    def __init__(self, panel_id: str, cog):
        self.panel_id = panel_id
        self.cog = cog
        
        options = [
            discord.SelectOption(label="🐛 Bug/Erro", value="bug", emoji="🐛"),
            discord.SelectOption(label="🚨 Denúncia", value="denuncia", emoji="🚨"),
            discord.SelectOption(label="💎 Contribuidor", value="contribuidor", emoji="💎"),
            discord.SelectOption(label="💰 Financeiro", value="financeiro", emoji="💰"),
            discord.SelectOption(label="🌟 Influencer/Parceria", value="influencer", emoji="🌟"),
            discord.SelectOption(label="❓ Dúvida", value="duvida", emoji="❓"),
            discord.SelectOption(label="🔧 Suporte Técnico", value="suporte", emoji="🔧"),
            discord.SelectOption(label="📌 Outro", value="outro", emoji="📌"),
        ]
        super().__init__(placeholder="Selecione a categoria...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        category_key = self.values[0]
        modal = OpenTicketModal(self.panel_id, category_key, self.cog)
        await interaction.response.send_modal(modal)

class CategoryView(View):
    """View com dropdown de categoria"""
    
    def __init__(self, panel_id: str, cog):
        super().__init__(timeout=300)
        self.add_item(CategorySelect(panel_id, cog))

class OpenTicketModal(Modal):
    """Modal para o usuário preencher ao abrir o ticket"""
    
    def __init__(self, panel_id: str, category_key: str, cog):
        super().__init__(title="Abrir Ticket")
        self.panel_id = panel_id
        self.category_key = category_key
        self.cog = cog
        
        self.subject = TextInput(
            label="Assunto",
            placeholder="Descreva resumidamente o motivo...",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.add_item(self.subject)
        
        self.description = TextInput(
            label="Descrição",
            placeholder="Detalhe o que está acontecendo...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.cog._create_ticket(
            interaction,
            self.panel_id,
            self.category_key,
            self.subject.value,
            self.description.value
        )

# ═══════════════ COG ═══════════════

class Tickets(commands.Cog):
    """Sistema de tickets"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self._panel_messages = {}
        self._staff_roles_cache = {}
        self.auto_close_inactive.start()
        
        logger.info(f"🔧 Tickets inicializado: api_url={self.api_url}")
    
    # ═══════════════ HELPERS ═══════════════
    
    async def _api_get(self, path: str) -> Optional[dict | list]:
        """Faz GET na API com Basic Auth"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.get(f"{self.api_url}{path}") as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API GET {path}: {e}")
        return None
    
    async def _api_post(self, path: str, json: dict) -> Optional[dict]:
        """Faz POST na API com Basic Auth"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(f"{self.api_url}{path}", json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API POST {path}: {e}")
        return None
    
    async def _api_put(self, path: str, json: dict) -> Optional[dict]:
        """Faz PUT na API com Basic Auth"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.put(f"{self.api_url}{path}", json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API PUT {path}: {e}")
        return None
    
    async def _get_staff_roles(self, guild_id: int) -> list:
        """Busca roles de staff, com cache"""
        if guild_id in self._staff_roles_cache:
            return self._staff_roles_cache[guild_id]
        
        data = await self._api_get(f"/guilds/{guild_id}/tickets/bot/staff-roles")
        roles = data if isinstance(data, list) else []
        self._staff_roles_cache[guild_id] = roles
        return roles
    
    async def _save_panel_message_id(self, guild_id: int, panel_id: str, message_id: int):
        result = await self._api_put(
            f"/guilds/{guild_id}/tickets/panels/{panel_id}/message",
            {"message_id": message_id}
        )
        if result:
            self._panel_messages[panel_id] = message_id
            logger.info(f"💾 message_id salvo: panel={panel_id} msg={message_id}")
    
    async def _get_panel_message(self, guild: discord.Guild, panel_id: str, channel_id: int):
        if panel_id in self._panel_messages:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    return await channel.fetch_message(self._panel_messages[panel_id])
                except discord.NotFound:
                    del self._panel_messages[panel_id]
        
        data = await self._api_get(f"/guilds/{guild.id}/tickets/panels/{panel_id}")
        if data and data.get("message_id"):
            msg_id = int(data["message_id"])
            self._panel_messages[panel_id] = msg_id
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    return await channel.fetch_message(msg_id)
                except discord.NotFound:
                    pass
        return None
    
    async def _get_ticket_info(self, guild_id: int, ticket_id: str) -> Optional[dict]:
        return await self._api_get(f"/guilds/{guild_id}/tickets/bot/{ticket_id}")
    
    async def _check_can_close(self, interaction: discord.Interaction, ticket_info: dict) -> tuple[bool, str]:
        user = interaction.user
        
        if user.guild_permissions.administrator:
            return True, "admin"
        
        # Verifica se usuário pode fechar
        if str(user.id) == str(ticket_info.get("user_id")):
            config = await self._api_get(f"/guilds/{interaction.guild.id}/tickets/bot/config")
            allow_user_close = config.get("allow_user_close", True) if config else True
            if allow_user_close:
                return True, "owner"
            else:
                return False, "Apenas staff pode fechar tickets."
        
        claimed_by = ticket_info.get("claimed_by")
        if claimed_by and str(user.id) == str(claimed_by):
            return True, "claimed"
        
        return False, "Você não tem permissão para fechar este ticket."
    
    async def _apply_ticket_permissions(self, channel, guild, user, claimed_by=None):
        staff_roles = await self._get_staff_roles(guild.id)
        
        # Busca config de attachments
        config = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
        allow_attachments = config.get("allow_attachments", True) if config else True
        
        base_perms = discord.PermissionOverwrite(
            read_messages=True, send_messages=True,
            attach_files=allow_attachments,
            embed_links=allow_attachments,
            add_reactions=True,
            read_message_history=True,
            use_external_emojis=True,
            use_external_stickers=True
        )
        
        overwrites = {}
        for target, perm in channel.overwrites.items():
            overwrites[target] = perm
        
        overwrites[user] = base_perms
        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True,
            attach_files=True, embed_links=True, add_reactions=True
        )
        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
        
        for sr in staff_roles:
            role = guild.get_role(int(sr["role_id"]))
            if role and sr.get("can_view_all"):
                overwrites[role] = base_perms
        
        for role in guild.roles:
            if role.permissions.administrator and role.name != "@everyone":
                overwrites[role] = base_perms
        
        if claimed_by:
            claimed_member = guild.get_member(int(claimed_by))
            if claimed_member:
                overwrites[claimed_member] = base_perms
        
        await channel.edit(overwrites=overwrites)
        
    async def _create_ticket(self, interaction, panel_id, category_key, subject, description):
        """Cria o ticket após preenchimento do modal"""
        
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        
        panel_data = await self._api_get(f"/guilds/{guild.id}/tickets/panels/{panel_id}")
        if not panel_data:
            await interaction.followup.send("❌ Painel não encontrado.", ephemeral=True)
            return
        
        config_data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
        allow_attachments = config_data.get("allow_attachments", True) if config_data else True
        max_open = config_data.get("max_open_tickets", 5) if config_data else 5
        
        if max_open > 0:
            tickets_data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/list?status=open&user_id={user.id}")
            open_count = tickets_data.get("total", 0) if tickets_data else 0
            
            if open_count >= max_open:
                await interaction.followup.send(
                    f"❌ Você já tem {open_count} ticket(s) aberto(s). Limite máximo: {max_open}.",
                    ephemeral=True
                )
                return
        
        ticket_count = (config_data.get("ticket_counter", 0) + 1) if config_data else 1
        
        category_id = panel_data.get("category_id")
        category = guild.get_channel(int(category_id)) if category_id else None
        
        channel_name = f"ticket-{ticket_count:04d}-{user.name}"
        
        category_priority = {
            "bug": "urgent",
            "denuncia": "urgent",
            "contribuidor": "high",
            "financeiro": "high",
            "influencer": "medium",
            "duvida": "medium",
            "suporte": "medium",
            "outro": "low",
        }

        priority = category_priority.get(category_key, "medium")
        
        topic = f"Ticket #{ticket_count} de {user.name} | {subject} | priority:{priority}"
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=topic,
                reason=f"Ticket aberto por {user.name}"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Não tenho permissão para criar canais.", ephemeral=True)
            return
        
        result = await self._api_post(f"/guilds/{guild.id}/tickets/open", {
            "user_id": str(user.id),
            "channel_id": str(channel.id),
            "panel_id": panel_id,
            "subject": subject,
            "description": description,
            "category": category_key,
            "priority": priority,
        })
        
        if not result:
            await channel.delete()
            await interaction.followup.send("❌ Erro ao registrar ticket.", ephemeral=True)
            return
        
        ticket_id = result.get("id")
        
        # Permissões
        staff_roles = await self._get_staff_roles(guild.id)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, attach_files=True, embed_links=True, add_reactions=True),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                attach_files=allow_attachments,
                embed_links=allow_attachments
            )
        }
        for sr in staff_roles:
            role = guild.get_role(int(sr["role_id"]))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role in guild.roles:
            if role.permissions.administrator and role.name != "@everyone":
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        await channel.edit(overwrites=overwrites)
        
        # Ordena por prioridade - agrupado por nível
        if category:
            await self._reorder_category(category)
        
        # Embed
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_count}",
            description=f"Olá {user.mention}, um membro da equipe irá atendê-lo em breve.\n\n**Assunto:** {subject}\n**Descrição:** {description}",
            color=discord.Color.green(),
        )
        embed.add_field(name="📝 Ticket ID", value=ticket_id, inline=True)
        embed.add_field(name="👤 Aberto por", value=user.mention, inline=True)
        embed.add_field(name="📂 Categoria", value=category_key, inline=True)
        embed.set_footer(text="Aguarde um staff liberar o chat.")
        
        view = TicketControlView(ticket_id=ticket_id)
        await channel.send(embed=embed, view=view)
        
        # Botão "Ir para o Ticket"
        link_view = View()
        link_view.add_item(Button(
            label="Ir para o Ticket",
            style=discord.ButtonStyle.link,
            url=channel.jump_url,
            emoji="🎫"
        ))
        await interaction.followup.send(
            f"🎫 Ticket #{ticket_count} aberto!",
            view=link_view,
            ephemeral=True
        )
        logger.info(f"✅ Ticket criado: {channel.id} ticket_id={ticket_id} categoria={category_key}")
        
    async def _close_ticket(self, interaction: discord.Interaction, ticket_id: str, reason: str, role: str = "claimed"):
        """Executa o fechamento do ticket"""
        
        guild = interaction.guild
        user = interaction.user
        channel = interaction.channel
        
        # 1️⃣ BLOQUEIA IMEDIATAMENTE - @everyone SEMPRE sem acesso
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
        }

        # Mantém permissões existentes de outros mas bloqueia send_messages
        for target, overwrite in channel.overwrites.items():
            if target == guild.default_role:
                continue  # Já tratado acima
            if isinstance(target, (discord.Member, discord.Role)):
                # Mantém read_messages como está, só bloqueia send_messages
                overwrites[target] = discord.PermissionOverwrite(
                    read_messages=overwrite.read_messages if overwrite.read_messages is not None else None,
                    send_messages=False
                )

        # Bot sempre tem acesso total
        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True
        )

        await channel.edit(overwrites=overwrites)

        # Envia a mensagem AGORA
        if role == "owner":
            title = "🔒 Ticket Fechado pelo Usuário"
            description = f"O usuário {user.mention} fechou este ticket."
        else:
            title = "🔒 Ticket Fechado"
            description = f"Ticket fechado por {user.mention}"

        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        embed.add_field(name="📝 Resolução", value=reason, inline=False)
        await channel.send(embed=embed)
        
        # 2️⃣ DEPOIS faz o resto (transcript, API, etc)
        ticket_info = await self._get_ticket_info(guild.id, ticket_id)
        opened_by_name = "Desconhecido"
        opened_by_id = ""
        opened_at = "Desconhecido"
        ticket_number = ""
        
        if ticket_info:
            opener_id = ticket_info.get("user_id")
            if opener_id:
                opener = guild.get_member(int(opener_id))
                if opener:
                    opened_by_name = str(opener)
                opened_by_id = str(opener_id)
            opened_at = ticket_info.get("created_at", "Desconhecido")
            ticket_number = str(ticket_info.get("ticket_number", ""))
        
        # Gera transcript
        transcript_url = None
        try:
            messages_data = []
            async for message in channel.history(oldest_first=True, limit=500):
                if message.author.bot and message.embeds:
                    continue
                
                messages_data.append({
                    "author_name": message.author.display_name,
                    "author_username": message.author.name,
                    "author_id": str(message.author.id),
                    "author_avatar": str(message.author.display_avatar.url),
                    "is_admin": message.author.guild_permissions.administrator if isinstance(message.author, discord.Member) else False,
                    "content": message.content,
                    "attachments": [
                        {
                            "url": a.url,
                            "filename": a.filename,
                            "content_type": a.content_type,
                            "size": a.size,
                            "is_image": a.content_type and "image" in a.content_type,
                            "is_video": a.content_type and "video" in a.content_type,
                        }
                        for a in message.attachments
                    ],
                    "stickers": [{"name": s.name, "url": str(s.url)} for s in message.stickers],
                    "embeds": [
                        {
                            "title": e.title, "description": e.description,
                            "url": e.url,
                            "image_url": str(e.image.url) if e.image else None,
                            "thumbnail_url": str(e.thumbnail.url) if e.thumbnail else None,
                        }
                        for e in message.embeds
                    ],
                    "timestamp": message.created_at.isoformat()
                })
            
            transcript_data = {
                "ticket_id": ticket_id,
                "ticket_number": ticket_number,
                "guild_id": str(guild.id),
                "guild_name": guild.name,
                "guild_icon": str(guild.icon.url) if guild.icon else None,
                "opened_by_name": opened_by_name,
                "opened_by_id": opened_by_id,
                "opened_at": opened_at,
                "closed_by_name": str(user),
                "closed_by_id": str(user.id),
                "close_reason": reason,
                "closed_at": discord.utils.utcnow().isoformat(),
                "messages": messages_data
            }
            
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(
                    f"{self.api_url}/guilds/{guild.id}/tickets/{ticket_id}/transcript",
                    json=transcript_data
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        transcript_url = data.get("url")
                        logger.info(f"📸 Transcript salvo: {transcript_url}")
        except Exception as e:
            logger.error(f"❌ Erro ao gerar/enviar transcript: {e}")
        
        # Fecha na API
        await self._api_post(
            f"/guilds/{guild.id}/tickets/{ticket_id}/bot/close",
            {"closed_by": str(user.id), "reason": reason}
        )
        
        # Envia transcript no canal configurado
        if transcript_url:
            config_data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
            transcript_channel_id = config_data.get("transcript_channel") if config_data else None
            
            if transcript_channel_id:
                transcript_channel = guild.get_channel(int(transcript_channel_id))
                if transcript_channel:
                    transcript_embed = discord.Embed(
                        title="📋 Ticket Fechado",
                        color=discord.Color.blue()
                    )
                    transcript_embed.add_field(name="📝 Nome do Ticket", value=f"ticket-{ticket_number}", inline=True)
                    transcript_embed.add_field(name="👤 Autor do Ticket", value=f"<@{opened_by_id}>", inline=True)
                    transcript_embed.add_field(name="🔒 Fechado por", value=user.mention, inline=True)
                    transcript_embed.add_field(name="📅 Data de Abertura", value=opened_at, inline=True)
                    transcript_embed.add_field(name="📅 Data de encerramento", value=discord.utils.utcnow().strftime("%d/%m/%Y %H:%M"), inline=True)
                    transcript_embed.add_field(name="📝 Motivo", value=reason, inline=False)
                    
                    view = View()
                    view.add_item(Button(
                        label="Ver Transcrição",
                        style=discord.ButtonStyle.link,
                        url=transcript_url,
                        emoji="📄"
                    ))
                    
                    await transcript_channel.send(embed=transcript_embed, view=view)
                    logger.info(f"📋 Transcript enviado em {transcript_channel.id}")
        
        # Deleta o canal
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket fechado por {user.name}")
            logger.info(f"🗑️ Canal deletado: {channel.id} ticket={ticket_id}")
        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para deletar canal: {channel.id}")
            
            
    async def _apply_chat_lock(self, channel, guild, locked: bool = True):
        """
        Bloqueia ou libera o chat para todos que não são staff.
        - Staff/admin: sempre pode falar
        - Usuário dono do ticket: controlado pelo parâmetro locked
        - Outros adicionados manualmente: controlado pelo parâmetro locked
        """
        
        staff_roles = await self._get_staff_roles(guild.id)
        
        # Coleta todos os IDs de roles de staff
        staff_role_ids = set()
        for sr in staff_roles:
            staff_role_ids.add(int(sr["role_id"]))
        
        # Admin role
        for role in guild.roles:
            if role.permissions.administrator:
                staff_role_ids.add(role.id)
        
        overwrites = {}
        
        # @everyone sempre sem acesso
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            read_messages=False, send_messages=False
        )
        
        # Bot sempre com acesso total
        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True,
            attach_files=True, embed_links=True, add_reactions=True
        )
        
        # Processa cada overwrite existente
        for target, overwrite in channel.overwrites.items():
            if target == guild.default_role or target == guild.me:
                continue
            
            if isinstance(target, discord.Role):
                if target.id in staff_role_ids:
                    # Staff role: sempre pode falar
                    overwrites[target] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    )
                else:
                    # Outra role: sem acesso
                    overwrites[target] = discord.PermissionOverwrite(
                        read_messages=False, send_messages=False
                    )
            
            elif isinstance(target, discord.Member):
                # Verifica se o membro é staff
                is_staff = target.guild_permissions.administrator
                if not is_staff:
                    for role in target.roles:
                        if role.id in staff_role_ids:
                            is_staff = True
                            break
                
                if is_staff:
                    # Staff: sempre pode falar
                    overwrites[target] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    )
                else:
                    # Não-staff: controlado pelo parâmetro locked
                    overwrites[target] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=not locked
                    )
        
        await channel.edit(overwrites=overwrites)
        logger.info(f"🔒 Chat {'bloqueado' if locked else 'liberado'} em {channel.name}")

    async def _change_priority(self, interaction, ticket_id, priority):
        await interaction.response.defer(ephemeral=True)
        valid = ["urgent", "high", "medium", "low"]
        if priority not in valid:
            await interaction.followup.send(f"❌ Prioridade inválida.", ephemeral=True)
            return
        await self._api_put(f"/guilds/{interaction.guild.id}/tickets/{ticket_id}/bot/priority", {"priority": priority})
        
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        new_priority_level = priority_order.get(priority, 2)
        channel = interaction.channel
        if channel.category:
            await self._reorder_category(channel.category)
        
        await interaction.followup.send(f"✅ Prioridade alterada para **{priority.upper()}**", ephemeral=True)
        
        
    async def _reorder_category(self, category):
        """Reordena todos os canais da categoria por prioridade + data (mais antigo primeiro)"""
        if not category:
            return
        
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        
        channels = [ch for ch in category.channels]
        
        def get_priority(ch):
            # Tenta extrair do tópico: "Ticket #1 de user | assunto | priority:urgent"
            if ch.topic and "priority:" in (ch.topic or ""):
                for p in priority_order:
                    if f"priority:{p}" in ch.topic:
                        return p
            return "medium"
        
        def sort_key(ch):
            p = get_priority(ch)
            return (priority_order.get(p, 2), ch.created_at.timestamp())
        
        sorted_channels = sorted(channels, key=sort_key)
        
        for i, ch in enumerate(sorted_channels):
            try:
                if ch.position != i:
                    await ch.edit(position=i)
            except:
                pass
        logger.info(f"📊 Categoria {category.name} reordenada ({len(channels)} canais)")
        
        
    @tasks.loop(minutes=1)
    async def auto_close_inactive(self):
        """Fecha tickets inativos após auto_close_hours"""
        from datetime import datetime, timezone
        
        for guild in self.bot.guilds:
            config = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
            if not config:
                continue
            
            auto_close_hours = config.get("auto_close_hours", 0)
            auto_close_hours = 0.016
            if auto_close_hours <= 0:
                continue
            
            tickets = await self._api_get(f"/guilds/{guild.id}/tickets/bot/list?status=open")
            if not tickets:
                continue
            
            now = datetime.now(timezone.utc)
            
            for ticket in tickets.get("tickets", []):
                channel = guild.get_channel(int(ticket["channel_id"]))
                if not channel:
                    continue
                
                # Busca última mensagem
                last_msg = None
                async for msg in channel.history(limit=1):
                    last_msg = msg
                    break
                
                if not last_msg:
                    continue
                
                # Se passou do tempo, fecha
                hours_inactive = (now - last_msg.created_at).total_seconds() / 3600
                if hours_inactive < auto_close_hours:
                    continue
                
                # Gera transcript
                messages_data = []
                async for message in channel.history(oldest_first=True, limit=500):
                    if message.author.bot and message.embeds:
                        continue
                    messages_data.append({
                        "author_name": message.author.display_name,
                        "author_username": message.author.name,
                        "author_id": str(message.author.id),
                        "author_avatar": str(message.author.display_avatar.url),
                        "content": message.content,
                        "attachments": [
                            {"url": a.url, "filename": a.filename, "content_type": a.content_type, "size": a.size}
                            for a in message.attachments
                        ],
                        "stickers": [{"name": s.name, "url": str(s.url)} for s in message.stickers],
                        "embeds": [
                            {"title": e.title, "description": e.description, "url": e.url}
                            for e in message.embeds
                        ],
                        "timestamp": message.created_at.isoformat()
                    })
                
                transcript_data = {
                    "ticket_id": ticket["id"],
                    "ticket_number": ticket.get("ticket_number", ""),
                    "guild_id": str(guild.id),
                    "guild_name": guild.name,
                    "guild_icon": str(guild.icon.url) if guild.icon else None,
                    "opened_by_name": ticket.get("user_name", "Desconhecido"),
                    "opened_by_id": str(ticket.get("user_id", "")),
                    "opened_at": ticket.get("created_at", ""),
                    "closed_by_name": str(self.bot.user),
                    "closed_by_id": str(self.bot.user.id),
                    "close_reason": f"Fechado automaticamente por inatividade ({auto_close_hours}h)",
                    "closed_at": discord.utils.utcnow().isoformat(),
                    "messages": messages_data
                }
                
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    await session.post(
                        f"{self.api_url}/guilds/{guild.id}/tickets/{ticket['id']}/transcript",
                        json=transcript_data
                    )
                
                await self._api_post(
                    f"/guilds/{guild.id}/tickets/{ticket['id']}/bot/close",
                    {
                        "closed_by": str(self.bot.user.id),
                        "reason": f"Fechado automaticamente por inatividade ({auto_close_hours}h)"
                    }
                )
                
                # Bloqueia e envia mensagem
                await channel.set_permissions(guild.default_role, send_messages=False)
                await channel.set_permissions(guild.me, send_messages=True)
                
                embed = discord.Embed(
                    title="⏰ Ticket Fechado por Inatividade",
                    description=f"Ticket fechado automaticamente após {auto_close_hours}h sem mensagens.",
                    color=discord.Color.orange()
                )
                await channel.send(embed=embed)
                
                await asyncio.sleep(5)
                try:
                    await channel.delete()
                except:
                    pass
                logger.info(f"⏰ Ticket {ticket['id']} fechado por inatividade em {guild.name}")

    @auto_close_inactive.before_loop
    async def before_auto_close(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.auto_close_inactive.cancel()
    
    # ═══════════════ REGISTRAR VIEWS NO STARTUP ═══════════════
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Registra views persistentes dos tickets abertos após restart"""
        if not self.bot.is_ready():
            return
        
        total_registered = 0
        for guild in self.bot.guilds:
            try:
                data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/list?status=open&limit=500")
                if not data:
                    continue
                
                tickets = data.get("tickets", [])
                for ticket in tickets:
                    ticket_id = ticket.get("id")
                    claimed_by = ticket.get("claimed_by")
                    if ticket_id:
                        self.bot.add_view(TicketControlView(ticket_id, claimed=(claimed_by is not None)))
                        total_registered += 1
                        logger.info(f"🔄 View registrada: ticket={ticket_id} guild={guild.name}")
            except Exception as e:
                logger.error(f"❌ Erro ao registrar views em {guild.name}: {e}")
        
        logger.info(f"✅ {total_registered} views de tickets abertos registradas")
    
    # ═══════════════ PANEL EVENTS ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_created(self, guild: discord.Guild, event):
        logger.info(f"🎨 Criando painel: guild={guild.id} panel={event.panel_id}")
        
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            return
        
        embed = discord.Embed(
            title=event.title,
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
        )
        
        view = TicketView(
            panel_id=event.panel_id,
            label=event.button_label or "Abrir Ticket",
            color=event.button_color or "blue"
        )
        
        message = await channel.send(embed=embed, view=view)
        await self._save_panel_message_id(guild.id, event.panel_id, message.id)
    
    @commands.Cog.listener()
    async def on_ticket_panel_updated(self, guild: discord.Guild, event):
        logger.info(f"✏️ Atualizando painel: guild={guild.id} panel={event.panel_id}")
        
        message = await self._get_panel_message(guild, event.panel_id, int(event.channel_id))
        
        embed = discord.Embed(
            title=event.title,
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
        )
        
        if event.is_active is False:
            embed.description = "🚫 Este painel foi desativado."
            view = None
        else:
            view = TicketView(
                panel_id=event.panel_id,
                label=event.button_label or "Abrir Ticket",
                color=event.button_color or "blue"
            )
        
        if message:
            await message.edit(embed=embed, view=view)
        else:
            channel = guild.get_channel(int(event.channel_id))
            if channel:
                message = await channel.send(embed=embed, view=view)
                await self._save_panel_message_id(guild.id, event.panel_id, message.id)
    
    @commands.Cog.listener()
    async def on_ticket_panel_deleted(self, guild: discord.Guild, panel_id: str):
        logger.info(f"🗑️ Removendo painel: guild={guild.id} panel={panel_id}")
        
        message_id = self._panel_messages.pop(panel_id, None)
        
        if not message_id:
            data = await self._api_get(f"/guilds/{guild.id}/tickets/panels/{panel_id}")
            if data and data.get("message_id"):
                message_id = int(data["message_id"])
        
        if not message_id:
            return
        
        for channel in guild.text_channels:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                logger.info(f"✅ Painel removido: panel={panel_id}")
                return
            except (discord.NotFound, discord.Forbidden):
                continue
    
    # ═══════════════ TICKET CLAIMED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_claimed(self, guild: discord.Guild, event):
        logger.info(f"👤 Ticket reivindicado: guild={guild.id} ticket={event.ticket_id}")
        
        channel_id = getattr(event, 'channel_id', None)
        if not channel_id:
            return
        
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return
        
        staff = guild.get_member(int(event.staff_id))
        if not staff:
            return
        
        ticket_info = await self._get_ticket_info(guild.id, event.ticket_id)
        if ticket_info:
            user = guild.get_member(int(ticket_info.get("user_id")))
            if user:
                await self._apply_ticket_permissions(
                    channel, guild, user,
                    claimed_by=str(event.staff_id)
                )
                # Libera chat automaticamente
                await channel.set_permissions(user, send_messages=True)
        
        embed = discord.Embed(
            title="👤 Ticket Atendido",
            description=f"{staff.mention} está atendendo este ticket.\n🔓 Chat liberado automaticamente.",
            color=discord.Color.blue(),
        )
        await channel.send(embed=embed)
    
    # ═══════════════ INTERACTIONS ═══════════════
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or "custom_id" not in interaction.data:
            return
        
        custom_id = interaction.data["custom_id"]
        
        # ═════════ ABRIR TICKET ═════════
        
        if custom_id.startswith("ticket_open_"):
            panel_id = custom_id.replace("ticket_open_", "")
            
            view = CategoryView(panel_id, self)
            await interaction.response.send_message(
                "📂 **Selecione a categoria do seu ticket:**",
                view=view,
                ephemeral=True
            )
        
        # ═════════ FECHAR TICKET ═════════
        
        elif custom_id.startswith("ticket_close_"):
            ticket_id = custom_id.replace("ticket_close_", "")
            
            ticket_info = await self._get_ticket_info(interaction.guild.id, ticket_id)
            if not ticket_info:
                await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
                return
            
            can_close, role = await self._check_can_close(interaction, ticket_info)
            
            if not can_close:
                await interaction.response.send_message(f"❌ {role}", ephemeral=True)
                return
            
            if role == "owner":
                view = ConfirmCloseView(ticket_id, self)
                await interaction.response.send_message(
                    "⚠️ Tem certeza que deseja fechar este ticket?",
                    view=view,
                    ephemeral=True
                )
            else:
                modal = CloseTicketModal(ticket_id, self)
                await interaction.response.send_modal(modal)
        
        # ═════════ CONFIRMAR FECHAMENTO ═════════
        
        elif custom_id.startswith("confirm_close_"):
            ticket_id = custom_id.replace("confirm_close_", "")
            await interaction.response.defer()
            await interaction.followup.send("✅ Fechando ticket...", ephemeral=True)
            await self._close_ticket(interaction, ticket_id, "Fechado pelo usuário", role="owner")
    
        elif custom_id.startswith("cancel_close_"):
            await interaction.response.edit_message(content="❌ Fechamento cancelado.", view=None)
        
        # ═════════ LIBERAR CHAT ═════════

        elif custom_id.startswith("ticket_unlock_") or custom_id.startswith("ticket_lock_") or custom_id.startswith("ticket_claim_"):
            
            # Verifica se é staff/admin primeiro
            if not interaction.user.guild_permissions.administrator:
                is_staff = False
                staff_roles = await self._get_staff_roles(interaction.guild.id)
                for sr in staff_roles:
                    role = interaction.guild.get_role(int(sr["role_id"]))
                    if role and role in interaction.user.roles:
                        is_staff = True
                        break
                
                if not is_staff:
                    await interaction.response.send_message("❌ Apenas staff pode usar este botão.", ephemeral=True)
                    return
            
            # ═════════ UNLOCK ═════════
            if custom_id.startswith("ticket_unlock_"):
                ticket_id = custom_id.replace("ticket_unlock_", "")
                
                ticket_info = await self._get_ticket_info(interaction.guild.id, ticket_id)
                if not ticket_info:
                    await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
                    return
                
                is_claimed = ticket_info.get("claimed_by") is not None
                
                await self._apply_chat_lock(interaction.channel, interaction.guild, locked=False)
                
                view = TicketControlView(ticket_id, chat_locked=False, claimed=is_claimed)
                await interaction.message.edit(view=view)
                
                embed = discord.Embed(
                    title="🔓 Chat Liberado",
                    description=f"O chat foi liberado por {interaction.user.mention}.",
                    color=discord.Color.blue(),
                )
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("✅ Chat liberado!", ephemeral=True)
            
            # ═════════ LOCK ═════════
            elif custom_id.startswith("ticket_lock_"):
                ticket_id = custom_id.replace("ticket_lock_", "")
                
                ticket_info = await self._get_ticket_info(interaction.guild.id, ticket_id)
                if not ticket_info:
                    await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
                    return
                
                is_claimed = ticket_info.get("claimed_by") is not None
                
                await self._apply_chat_lock(interaction.channel, interaction.guild, locked=True)
                
                view = TicketControlView(ticket_id, chat_locked=True, claimed=is_claimed)
                await interaction.message.edit(view=view)
                
                embed = discord.Embed(
                    title="🔒 Chat Bloqueado",
                    description=f"O chat foi bloqueado por {interaction.user.mention}.",
                    color=discord.Color.orange(),
                )
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("✅ Chat bloqueado!", ephemeral=True)
            
            # ═════════ CLAIM ═════════
            elif custom_id.startswith("ticket_claim_"):
                ticket_id = custom_id.replace("ticket_claim_", "")
                
                result = await self._api_put(
                    f"/guilds/{interaction.guild.id}/tickets/{ticket_id}/claim",
                    {"staff_id": str(interaction.user.id)}
                )
                
                if result:
                    ticket_info = await self._get_ticket_info(interaction.guild.id, ticket_id)
                    if ticket_info:
                        user_id = ticket_info.get("user_id")
                        user = interaction.guild.get_member(int(user_id)) if user_id else None
                        if user:
                            await self._apply_ticket_permissions(
                                interaction.channel, interaction.guild, user,
                                claimed_by=str(interaction.user.id))
                            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
                            
                            try:
                                view = TicketControlView(ticket_id, chat_locked=False, claimed=True)
                                await interaction.message.edit(view=view)
                            except:
                                pass
                            
                            embed = discord.Embed(
                                title="👤 Ticket Atendido",
                                description=f"{interaction.user.mention} está atendendo este ticket.\n🔓 Chat liberado automaticamente.",
                                color=discord.Color.blue(),
                            )
                            await interaction.channel.send(embed=embed)
                    
                    await interaction.response.send_message("👤 Ticket reivindicado! Chat liberado.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Erro ao reivindicar ticket.", ephemeral=True)
            
        elif custom_id.startswith("ticket_add_"):
            ticket_id = custom_id.replace("ticket_add_", "")
            view = AddMemberView(ticket_id, self)
            await interaction.response.send_message("👤 Selecione um usuário para adicionar:", view=view, ephemeral=True)

        elif custom_id.startswith("ticket_remove_"):
            ticket_id = custom_id.replace("ticket_remove_", "")
            view = RemoveMemberView(ticket_id, self)
            await interaction.response.send_message("👤 Selecione um usuário para remover:", view=view, ephemeral=True)

        elif custom_id.startswith("ticket_transfer_"):
            ticket_id = custom_id.replace("ticket_transfer_", "")
            view = TransferSelectView(ticket_id, self)
            await interaction.response.send_message("🔄 Selecione um staff para transferir:", view=view, ephemeral=True)

        elif custom_id.startswith("ticket_priority_"):
            ticket_id = custom_id.replace("ticket_priority_", "")
            view = PriorityView(ticket_id, self)
            await interaction.response.send_message("⚠️ Selecione a nova prioridade:", view=view, ephemeral=True)
        
        elif custom_id.startswith("ticket_addrole_"):
            ticket_id = custom_id.replace("ticket_addrole_", "")
            view = AddRoleView(ticket_id, self)
            await interaction.response.send_message("👔 Selecione um cargo para adicionar:", view=view, ephemeral=True)

        elif custom_id.startswith("ticket_removerole_"):
            ticket_id = custom_id.replace("ticket_removerole_", "")
            view = RemoveRoleView(ticket_id, self)
            await interaction.response.send_message("👔 Selecione um cargo para remover:", view=view, ephemeral=True)
                                
async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))