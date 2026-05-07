import discord
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

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
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Aqui a API valida se o usuário pode abrir ticket
        # Por enquanto, permite todos
        return True

class Tickets(commands.Cog):
    """Sistema de tickets"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = bot.config.API_URL if hasattr(bot, 'config') else None
    
    # ═══════════════ PANEL CREATED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_created(self, guild: discord.Guild, event):
        """Cria embed do painel no Discord"""
        
        # Busca o canal onde o painel deve ser enviado
        # O channel_id deveria vir no evento, mas não está no schema atual
        # Assumindo que o painel já tem um channel_id associado via API
        
        logger.info(f"🎨 Painel criado: guild={guild.id} panel={event.panel_id} '{event.title}'")
        
        # Se não tem channel_id no evento, não faz nada (API deve enviar)
        if not hasattr(event, 'channel_id') or not event.channel_id:
            logger.warning("Painel sem channel_id, ignorando criação do embed")
            return
        
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            logger.error(f"Canal {event.channel_id} não encontrado")
            return
        
        embed = discord.Embed(
            title=event.title or "Abrir Ticket",
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Sistema de Tickets")
        
        view = TicketView(
            panel_id=event.panel_id,
            label=event.button_label or "Abrir Ticket",
            color=event.button_color or "blue"
        )
        
        message = await channel.send(embed=embed, view=view)
        logger.info(f"✅ Embed do painel enviado: msg_id={message.id} channel={channel.id}")
        
        # TODO: salvar message_id na API para futuras atualizações
    
    # ═══════════════ PANEL UPDATED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_updated(self, guild: discord.Guild, event):
        """Atualiza embed do painel"""
        
        logger.info(f"✏️ Painel atualizado: guild={guild.id} panel={event.panel_id}")
        
        if not hasattr(event, 'message_id') or not hasattr(event, 'channel_id'):
            logger.warning("Painel sem message_id ou channel_id")
            return
        
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(int(event.message_id))
        except discord.NotFound:
            logger.error(f"Mensagem do painel não encontrada: {event.message_id}")
            return
        
        embed = discord.Embed(
            title=event.title or "Abrir Ticket",
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Sistema de Tickets")
        
        # Se desativado, remove botão
        if event.is_active is False:
            embed.description = "🚫 Este painel foi desativado."
            view = None
        else:
            view = TicketView(
                panel_id=event.panel_id,
                label=event.button_label or "Abrir Ticket",
                color=event.button_color or "blue"
            )
        
        await message.edit(embed=embed, view=view)
        logger.info(f"✅ Painel atualizado: msg_id={message.id}")
    
    # ═══════════════ PANEL DELETED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_deleted(self, guild: discord.Guild, panel_id: str):
        """Remove/desativa painel"""
        logger.info(f"🗑️ Painel deletado: guild={guild.id} panel={panel_id}")
        # A API deve ter removido a mensagem ou enviado panel/updated com is_active=false antes
        pass
    
    # ═══════════════ TICKET CREATED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_created(self, guild: discord.Guild, event):
        """Configura canal do ticket recém-criado"""
        
        logger.info(f"🎫 Ticket criado: guild={guild.id} ticket={event.ticket_id}")
        
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            logger.error(f"Canal do ticket não encontrado: {event.channel_id}")
            return
        
        user = guild.get_member(int(event.user_id))
        if not user:
            user = await self.bot.fetch_user(int(event.user_id))
        
        # Embed de boas-vindas
        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"Olá {user.mention}, um membro da equipe irá atendê-lo em breve.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📝 Ticket ID", value=event.ticket_id, inline=True)
        embed.add_field(name="👤 Aberto por", value=user.mention, inline=True)
        embed.set_footer(text="Para fechar, um staff usará o comando de fechar ticket.")
        
        # Botões de controle (staff)
        view = TicketControlView(ticket_id=event.ticket_id)
        
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Mensagem de boas-vindas enviada em {channel.id}")
    
    # ═══════════════ TICKET CLOSED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_closed(self, guild: discord.Guild, event):
        """Processa fechamento de ticket"""
        
        logger.info(f"🔒 Ticket fechado: guild={guild.id} ticket={event.ticket_id}")
        
        # O canal deve ser deletado ou arquivado pela API
        # Aqui só notificamos se necessário
        
        if hasattr(event, 'channel_id') and event.channel_id:
            channel = guild.get_channel(int(event.channel_id))
            if channel:
                closed_by = guild.get_member(int(event.closed_by)) if event.closed_by else None
                closer_name = closed_by.mention if closed_by else "Sistema"
                
                embed = discord.Embed(
                    title="🔒 Ticket Fechado",
                    description=f"Este ticket foi fechado por {closer_name}.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                if event.reason:
                    embed.add_field(name="📝 Motivo", value=event.reason, inline=False)
                
                await channel.send(embed=embed)
                logger.info(f"✅ Mensagem de fechamento enviada")
    
    # ═══════════════ TICKET CLAIMED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_claimed(self, guild: discord.Guild, event):
        """Notifica que um staff reivindicou o ticket"""
        
        logger.info(f"👤 Ticket reivindicado: guild={guild.id} ticket={event.ticket_id}")
        
        # O channel_id deveria vir no evento
        staff = guild.get_member(int(event.staff_id))
        if not staff:
            return
        
        # TODO: buscar channel_id do ticket na API ou ter no evento
        logger.info(f"✅ {staff.display_name} está atendendo o ticket {event.ticket_id}")
    
    # ═══════════════ BOTÃO DE ABRIR TICKET ═══════════════
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Processa clique no botão de abrir ticket"""
        
        if not interaction.data or "custom_id" not in interaction.data:
            return
        
        custom_id = interaction.data["custom_id"]
        
        if custom_id.startswith("ticket_open_"):
            panel_id = custom_id.replace("ticket_open_", "")
            logger.info(f"🎫 Usuário {interaction.user.id} solicitou abertura de ticket via painel {panel_id}")
            
            # Notifica API para criar o ticket
            # A API vai criar o canal e notificar o bot de volta via ticket/created
            # Por enquanto, responde ao usuário
            await interaction.response.send_message(
                "🎫 Sua solicitação de ticket foi enviada! Aguarde...",
                ephemeral=True
            )
        
        elif custom_id.startswith("ticket_close_"):
            ticket_id = custom_id.replace("ticket_close_", "")
            await interaction.response.send_message(
                f"🔒 Solicitação de fechamento do ticket {ticket_id} enviada.",
                ephemeral=True
            )
        
        elif custom_id.startswith("ticket_claim_"):
            ticket_id = custom_id.replace("ticket_claim_", "")
            await interaction.response.send_message(
                f"👤 Você reivindicou o ticket {ticket_id}.",
                ephemeral=True
            )


class TicketControlView(View):
    """Botões de controle do ticket (staff)"""
    
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        
        self.add_item(Button(
            label="Fechar",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket_close_{ticket_id}",
            emoji="🔒"
        ))
        
        self.add_item(Button(
            label="Atender",
            style=discord.ButtonStyle.success,
            custom_id=f"ticket_claim_{ticket_id}",
            emoji="👤"
        ))

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))