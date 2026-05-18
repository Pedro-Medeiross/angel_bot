import discord
from discord.ui import View

async def handle_interaction(cog, interaction: discord.Interaction):
    """Processa todas as interações de ticket"""
    if not interaction.data or "custom_id" not in interaction.data:
        return
    
    custom_id = interaction.data["custom_id"]
    
    if "feedback" in custom_id:
        print(f"⭐ DEBUG feedback custom_id: {custom_id}")
    
    # ═════════ ABRIR TICKET ═════════
    if custom_id.startswith("ticket_open_"):
        panel_id = custom_id.replace("ticket_open_", "")
        categories = await cog._get_categories(interaction.guild.id)
        if not categories:
            await interaction.response.send_message("❌ Nenhuma categoria disponível.", ephemeral=True)
            return
        from .views import CategoryView
        view = CategoryView(panel_id, cog, categories)
        await interaction.response.send_message("📂 **Selecione a categoria do seu ticket:**", view=view, ephemeral=True)
        return
    
    # ═════════ FECHAR TICKET ═════════
    if custom_id.startswith("ticket_close_"):
        ticket_id = custom_id.replace("ticket_close_", "")
        ticket_info = await cog._get_ticket_info(interaction.guild.id, ticket_id)
        if not ticket_info:
            await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
            return
        can_close, role = await cog._check_can_close(interaction, ticket_info)
        if not can_close:
            await interaction.response.send_message(f"❌ {role}", ephemeral=True)
            return
        if role == "owner":
            from .views import ConfirmCloseView
            view = ConfirmCloseView(ticket_id, cog)
            await interaction.response.send_message("⚠️ Tem certeza que deseja fechar este ticket?", view=view, ephemeral=True)
        else:
            from .views import CloseTicketModal
            modal = CloseTicketModal(ticket_id, cog)
            await interaction.response.send_modal(modal)
        return
    
    # ═════════ CONFIRMAR FECHAMENTO ═════════
    if custom_id.startswith("confirm_close_"):
        ticket_id = custom_id.replace("confirm_close_", "")
        await interaction.response.defer()
        await interaction.followup.send("✅ Fechando ticket...", ephemeral=True)
        await cog._close_ticket(interaction, ticket_id, "Fechado pelo usuário", role="owner")
        return
    
    if custom_id.startswith("cancel_close_"):
        await interaction.response.edit_message(content="❌ Fechamento cancelado.", view=None)
        return
    
    # ═════════ UNLOCK / LOCK / CLAIM ═════════
    if custom_id.startswith("ticket_unlock_") or custom_id.startswith("ticket_lock_") or custom_id.startswith("ticket_claim_"):
        if not interaction.user.guild_permissions.administrator:
            is_staff = False
            staff_roles = await cog._get_staff_roles(interaction.guild.id)
            for sr in staff_roles:
                role = interaction.guild.get_role(int(sr["role_id"]))
                if role and role in interaction.user.roles:
                    is_staff = True
                    break
            if not is_staff:
                await interaction.response.send_message("❌ Apenas staff pode usar este botão.", ephemeral=True)
                return
        
        if custom_id.startswith("ticket_unlock_"):
            ticket_id = custom_id.replace("ticket_unlock_", "")
            ticket_info = await cog._get_ticket_info(interaction.guild.id, ticket_id)
            if not ticket_info:
                await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
                return
            is_claimed = ticket_info.get("claimed_by") is not None
            await cog._apply_chat_lock(interaction.channel, interaction.guild, locked=False)
            from .views import TicketControlView
            view = TicketControlView(ticket_id, chat_locked=False, claimed=is_claimed)
            await interaction.message.edit(view=view)
            embed = discord.Embed(title="🔓 Chat Liberado", description=f"O chat foi liberado por {interaction.user.mention}.", color=discord.Color.blue())
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ Chat liberado!", ephemeral=True)
        
        elif custom_id.startswith("ticket_lock_"):
            ticket_id = custom_id.replace("ticket_lock_", "")
            ticket_info = await cog._get_ticket_info(interaction.guild.id, ticket_id)
            if not ticket_info:
                await interaction.response.send_message("❌ Ticket não encontrado.", ephemeral=True)
                return
            is_claimed = ticket_info.get("claimed_by") is not None
            await cog._apply_chat_lock(interaction.channel, interaction.guild, locked=True)
            from .views import TicketControlView
            view = TicketControlView(ticket_id, chat_locked=True, claimed=is_claimed)
            await interaction.message.edit(view=view)
            embed = discord.Embed(title="🔒 Chat Bloqueado", description=f"O chat foi bloqueado por {interaction.user.mention}.", color=discord.Color.orange())
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ Chat bloqueado!", ephemeral=True)
        
        elif custom_id.startswith("ticket_claim_"):
            ticket_id = custom_id.replace("ticket_claim_", "")
            result = await cog._api_put(f"/guilds/{interaction.guild.id}/tickets/{ticket_id}/claim", {"staff_id": str(interaction.user.id)})
            if result:
                ticket_info = await cog._get_ticket_info(interaction.guild.id, ticket_id)
                if ticket_info:
                    user_id = ticket_info.get("user_id")
                    user = interaction.guild.get_member(int(user_id)) if user_id else None
                    if user:
                        await cog._apply_ticket_permissions(interaction.channel, interaction.guild, user, claimed_by=str(interaction.user.id))
                        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
                        from .views import TicketControlView
                        view = TicketControlView(ticket_id, chat_locked=False, claimed=True)
                        try:
                            await interaction.message.edit(view=view)
                        except:
                            pass
                        embed = discord.Embed(title="👤 Ticket Atendido", description=f"{interaction.user.mention} está atendendo este ticket.\n🔓 Chat liberado automaticamente.", color=discord.Color.blue())
                        await interaction.channel.send(embed=embed)
                await interaction.response.send_message("👤 Ticket reivindicado! Chat liberado.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Erro ao reivindicar ticket.", ephemeral=True)
        return
    
    # ═════════ ADD MEMBER ═════════
    if custom_id.startswith("ticket_add_"):
        ticket_id = custom_id.replace("ticket_add_", "")
        from .views import AddMemberView
        view = AddMemberView(ticket_id, cog)
        await interaction.response.send_message("👤 Selecione um usuário para adicionar:", view=view, ephemeral=True)
        return
    
    # ═════════ REMOVE MEMBER ═════════
    if custom_id.startswith("ticket_remove_"):
        ticket_id = custom_id.replace("ticket_remove_", "")
        from .views import RemoveMemberView
        view = RemoveMemberView(ticket_id, cog)
        await interaction.response.send_message("👤 Selecione um usuário para remover:", view=view, ephemeral=True)
        return
    
    # ═════════ TRANSFER ═════════
    if custom_id.startswith("ticket_transfer_"):
        ticket_id = custom_id.replace("ticket_transfer_", "")
        from .views import TransferSelectView
        view = TransferSelectView(ticket_id, cog)
        await interaction.response.send_message("🔄 Selecione um staff para transferir:", view=view, ephemeral=True)
        return
    
    # ═════════ PRIORITY ═════════
    if custom_id.startswith("ticket_priority_"):
        ticket_id = custom_id.replace("ticket_priority_", "")
        from .views import PriorityView
        view = PriorityView(ticket_id, cog)
        await interaction.response.send_message("⚠️ Selecione a nova prioridade:", view=view, ephemeral=True)
        return
    
    # ═════════ ADD ROLE ═════════
    if custom_id.startswith("ticket_addrole_"):
        ticket_id = custom_id.replace("ticket_addrole_", "")
        from .views import AddRoleView
        view = AddRoleView(ticket_id, cog)
        await interaction.response.send_message("👔 Selecione um cargo para adicionar:", view=view, ephemeral=True)
        return
    
    # ═════════ REMOVE ROLE ═════════
    if custom_id.startswith("ticket_removerole_"):
        ticket_id = custom_id.replace("ticket_removerole_", "")
        from .views import RemoveRoleView
        view = RemoveRoleView(ticket_id, cog)
        await interaction.response.send_message("👔 Selecione um cargo para remover:", view=view, ephemeral=True)
        return