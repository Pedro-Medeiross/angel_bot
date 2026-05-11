import discord
from discord.ext import commands
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
    """Botões de controle do ticket (staff)"""
    
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        
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
        await self.cog._close_ticket(interaction, self.ticket_id, self.reason.value)

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
        
        if str(user.id) == str(ticket_info.get("user_id")):
            return True, "owner"
        
        claimed_by = ticket_info.get("claimed_by")
        if claimed_by and str(user.id) == str(claimed_by):
            return True, "claimed"
        
        return False, "Você não tem permissão para fechar este ticket."
    
    async def _apply_ticket_permissions(self, channel: discord.TextChannel, guild: discord.Guild, user: discord.Member, claimed_by: str = None):
        """Aplica permissões no canal do ticket"""
        
        staff_roles = await self._get_staff_roles(guild.id)
        
        base_perms = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            read_message_history=True,
            use_external_emojis=True,
            use_external_stickers=True
        )
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True,
                attach_files=True, embed_links=True, add_reactions=True
            ),
            user: base_perms
        }
        
        if claimed_by:
            claimed_member = guild.get_member(int(claimed_by))
            if claimed_member:
                overwrites[claimed_member] = base_perms
        
        for sr in staff_roles:
            role = guild.get_role(int(sr["role_id"]))
            if role and sr.get("can_view_all"):
                overwrites[role] = base_perms
        
        for role in guild.roles:
            if role.permissions.administrator and role.name != "@everyone":
                overwrites[role] = base_perms
        
        await channel.edit(overwrites=overwrites)
        logger.info(f"🔒 Permissões aplicadas em {channel.name}")
    
    async def _close_ticket(self, interaction: discord.Interaction, ticket_id: str, reason: str):
        """Executa o fechamento do ticket"""
        
        guild = interaction.guild
        user = interaction.user
        
        result = await self._api_post(
            f"/guilds/{guild.id}/tickets/{ticket_id}/close",
            {"reason": reason}
        )
        
        if result:
            embed = discord.Embed(
                title="🔒 Ticket Fechado",
                description=f"Ticket fechado por {user.mention}",
                color=discord.Color.red(),
            )
            embed.add_field(name="📝 Resolução", value=reason, inline=False)
            
            await interaction.channel.send(embed=embed)
            logger.info(f"🔒 Ticket fechado: {ticket_id} por {user.id}")
    
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
                    if ticket_id:
                        self.bot.add_view(TicketControlView(ticket_id))
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
        
        embed = discord.Embed(
            title="👤 Ticket Atendido",
            description=f"{staff.mention} está atendendo este ticket.",
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
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                guild = interaction.guild
                user = interaction.user
                
                panel_data = await self._api_get(f"/guilds/{guild.id}/tickets/panels/{panel_id}")
                if not panel_data:
                    await interaction.followup.send("❌ Painel não encontrado.", ephemeral=True)
                    return
                
                config_data = await self._api_get(f"/guilds/{guild.id}/tickets/config")
                ticket_count = (config_data.get("ticket_counter", 0) + 1) if config_data else 1
                
                category_id = panel_data.get("category_id")
                category = guild.get_channel(int(category_id)) if category_id else None
                
                channel_name = f"ticket-{ticket_count:04d}-{user.name}"
                
                try:
                    channel = await guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        topic=f"Ticket #{ticket_count} de {user.name}",
                        reason=f"Ticket aberto por {user.name}"
                    )
                except discord.Forbidden:
                    await interaction.followup.send("❌ Não tenho permissão para criar canais.", ephemeral=True)
                    return
                
                result = await self._api_post(f"/guilds/{guild.id}/tickets/open", {
                    "user_id": str(user.id),
                    "channel_id": str(channel.id),
                    "panel_id": panel_id
                })
                
                if not result:
                    await channel.delete()
                    await interaction.followup.send("❌ Erro ao registrar ticket.", ephemeral=True)
                    return
                
                ticket_id = result.get("id")
                
                await self._apply_ticket_permissions(channel, guild, user)
                
                embed = discord.Embed(
                    title=f"🎫 Ticket #{ticket_count}",
                    description=f"Olá {user.mention}, um membro da equipe irá atendê-lo em breve.",
                    color=discord.Color.green(),
                )
                embed.add_field(name="📝 Ticket ID", value=ticket_id, inline=True)
                embed.add_field(name="👤 Aberto por", value=user.mention, inline=True)
                embed.set_footer(text="Use os botões abaixo para gerenciar o ticket.")
                
                view = TicketControlView(ticket_id=ticket_id)
                await channel.send(embed=embed, view=view)
                
                await interaction.followup.send(
                    f"🎫 Ticket #{ticket_count} aberto! {channel.mention}",
                    ephemeral=True
                )
                logger.info(f"✅ Ticket criado: {channel.id} ticket_id={ticket_id} número=#{ticket_count}")
            
            except aiohttp.ClientError as e:
                await interaction.followup.send("❌ Erro ao comunicar com a API.", ephemeral=True)
                logger.error(f"❌ Erro ticket_open: {e}")
        
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
            modal = CloseTicketModal(ticket_id, self)
            await interaction.response.send_modal(modal)
        
        elif custom_id.startswith("cancel_close_"):
            await interaction.response.edit_message(content="❌ Fechamento cancelado.", view=None)
        
        # ═════════ CLAIM TICKET ═════════
        
        elif custom_id.startswith("ticket_claim_"):
            ticket_id = custom_id.replace("ticket_claim_", "")
            
            result = await self._api_put(
                f"/guilds/{interaction.guild.id}/tickets/{ticket_id}/claim",
                {"staff_id": str(interaction.user.id)}
            )
            
            if result:
                await interaction.response.send_message("👤 Ticket reivindicado!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Erro ao reivindicar ticket.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))