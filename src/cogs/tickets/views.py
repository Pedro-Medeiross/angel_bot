import discord
from discord.ui import View, Button, Modal, TextInput
from typing import Optional

# ═══════════════ TICKET VIEW (PAINEL) ═══════════════

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
            label=label, style=style,
            custom_id=f"ticket_open_{panel_id}",
            emoji="🎫"
        ))

# ═══════════════ TICKET CONTROL VIEW ═══════════════

class TicketControlView(View):
    """Botões de controle do ticket"""
    
    def __init__(self, ticket_id: str, chat_locked: bool = True, claimed: bool = False):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        
        if not claimed:
            if chat_locked:
                self.add_item(Button(label="Liberar Chat", style=discord.ButtonStyle.primary, custom_id=f"ticket_unlock_{ticket_id}", emoji="🔓", row=0))
            else:
                self.add_item(Button(label="Bloquear Chat", style=discord.ButtonStyle.secondary, custom_id=f"ticket_lock_{ticket_id}", emoji="🔒", row=0))
            self.add_item(Button(label="Atender", style=discord.ButtonStyle.success, custom_id=f"ticket_claim_{ticket_id}", emoji="👤", row=0))
            self.add_item(Button(label="Fechar", style=discord.ButtonStyle.danger, custom_id=f"ticket_close_{ticket_id}", emoji="🔒", row=0))
        else:
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

# ═══════════════ ADD MEMBER ═══════════════

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
            embed = discord.Embed(title="➕ Membro Adicionado", description=f"{member.mention} foi adicionado ao ticket por {interaction.user.mention}.", color=discord.Color.green())
            await interaction.channel.send(embed=embed)
        else:
            await interaction.response.send_message("❌ Usuário não encontrado no servidor.", ephemeral=True)

# ═══════════════ REMOVE MEMBER ═══════════════

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
            embed = discord.Embed(title="➖ Membro Removido", description=f"{member.mention} foi removido do ticket por {interaction.user.mention}.", color=discord.Color.orange())
            await interaction.channel.send(embed=embed)

# ═══════════════ ADD ROLE ═══════════════

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
        embed = discord.Embed(title="➕ Cargo Adicionado", description=f"Cargo {role.mention} foi adicionado ao ticket por {interaction.user.mention}.", color=discord.Color.green())
        await interaction.channel.send(embed=embed)

class AddRoleView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(AddRoleSelect(ticket_id, cog))

# ═══════════════ REMOVE ROLE ═══════════════

class RemoveRoleSelect(discord.ui.RoleSelect):
    def __init__(self, ticket_id: str, cog):
        self.ticket_id = ticket_id
        self.cog = cog
        super().__init__(placeholder="Selecione um cargo para remover...", min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        overwrite = interaction.channel.overwrites_for(role)
        if overwrite.is_empty() or not overwrite.read_messages:
            await interaction.response.send_message("❌ Este cargo não está no ticket.", ephemeral=True)
            return
        await interaction.channel.set_permissions(role, overwrite=None)
        await interaction.response.send_message(f"✅ Cargo {role.mention} removido do ticket.", ephemeral=True)
        embed = discord.Embed(title="➖ Cargo Removido", description=f"Cargo {role.mention} foi removido do ticket por {interaction.user.mention}.", color=discord.Color.orange())
        await interaction.channel.send(embed=embed)

class RemoveRoleView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=120)
        self.add_item(RemoveRoleSelect(ticket_id, cog))

# ═══════════════ TRANSFER ═══════════════

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
        await self.cog._api_post(f"/guilds/{interaction.guild.id}/tickets/{self.ticket_id}/bot/transfer", {"to_staff_id": str(member.id)})
        await interaction.response.send_message(f"✅ Ticket transferido para {member.mention}.", ephemeral=True)
        embed = discord.Embed(title="🔄 Ticket Transferido", description=f"Ticket transferido para {member.mention} por {interaction.user.mention}.", color=discord.Color.blue())
        await interaction.channel.send(embed=embed)

# ═══════════════ PRIORITY ═══════════════

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
        await self.cog._api_put(f"/guilds/{interaction.guild.id}/tickets/{self.ticket_id}/bot/priority", {"priority": priority})
        if interaction.channel.category:
            await self.cog._reorder_category(interaction.channel.category)
        await interaction.response.send_message(f"✅ Prioridade alterada para **{priority.upper()}**", ephemeral=True)

class PriorityView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=60)
        self.add_item(PrioritySelect(ticket_id, cog))

# ═══════════════ CLOSE TICKET MODAL ═══════════════

class CloseTicketModal(Modal):
    def __init__(self, ticket_id: str, cog):
        super().__init__(title="Fechar Ticket")
        self.ticket_id = ticket_id
        self.cog = cog
        self.reason = TextInput(label="Mensagem de resolução", placeholder="Descreva o que foi resolvido...", style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ticket_info = await self.cog._get_ticket_info(interaction.guild.id, self.ticket_id)
        role = "owner" if ticket_info and str(interaction.user.id) == str(ticket_info.get("user_id")) else "claimed"
        await self.cog._close_ticket(interaction, self.ticket_id, self.reason.value, role)

class ConfirmCloseView(View):
    def __init__(self, ticket_id: str, cog):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.cog = cog
        self.add_item(Button(label="Confirmar fechamento", style=discord.ButtonStyle.danger, custom_id=f"confirm_close_{ticket_id}", emoji="✅"))
        self.add_item(Button(label="Cancelar", style=discord.ButtonStyle.secondary, custom_id=f"cancel_close_{ticket_id}", emoji="❌"))
    
    async def on_timeout(self):
        if hasattr(self, 'message') and self.message:
            await self.message.edit(content="⏰ Tempo esgotado.", view=None)

# ═══════════════ CATEGORY ═══════════════

class CategorySelect(discord.ui.Select):
    def __init__(self, panel_id: str, cog, categories: list):
        self.panel_id = panel_id
        self.cog = cog
        self.categories = categories
        options = [discord.SelectOption(label=c["label"], value=c["name"], emoji=c.get("emoji", "")) for c in categories]
        super().__init__(placeholder="Selecione a categoria...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        category_key = self.values[0]
        priority = "medium"
        for c in self.categories:
            if c["name"] == category_key:
                priority = c.get("priority", "medium")
                break
        modal = OpenTicketModal(self.panel_id, category_key, priority, self.cog)
        await interaction.response.send_modal(modal)

class CategoryView(View):
    def __init__(self, panel_id: str, cog, categories: list):
        super().__init__(timeout=300)
        self.add_item(CategorySelect(panel_id, cog, categories))

class OpenTicketModal(Modal):
    def __init__(self, panel_id: str, category_key: str, priority: str, cog):
        super().__init__(title="Abrir Ticket")
        self.panel_id = panel_id
        self.category_key = category_key
        self.priority = priority
        self.cog = cog
        self.subject = TextInput(label="Assunto", placeholder="Descreva resumidamente o motivo...", style=discord.TextStyle.short, required=True, max_length=100)
        self.add_item(self.subject)
        self.description = TextInput(label="Descrição", placeholder="Detalhe o que está acontecendo...", style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.cog._create_ticket(interaction, self.panel_id, self.category_key, self.priority, self.subject.value, self.description.value)