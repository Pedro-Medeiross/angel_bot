import discord
from discord.ext import commands
from discord.ui import View, Button
import aiohttp
from typing import Optional
import logging
from src.core.config import config

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

class Tickets(commands.Cog):
    """Sistema de tickets"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self._panel_messages = {}
        
        logger.info(f"🔧 Tickets inicializado: api_url={self.api_url} user={self.api_user[:5]}...")
    
    async def _save_panel_message_id(self, guild_id: int, panel_id: str, message_id: int):
        """Salva o message_id do painel na API via Basic Auth"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/guilds/{guild_id}/tickets/panels/{panel_id}/message"
                
                async with session.put(
                    url, 
                    json={"message_id": message_id},
                    auth=self.auth
                ) as resp:
                    if resp.status == 200:
                        self._panel_messages[panel_id] = message_id
                        logger.info(f"💾 message_id salvo: panel={panel_id} msg={message_id}")
                    else:
                        body = await resp.text()
                        logger.error(f"❌ Erro ao salvar message_id: {resp.status} - {body}")
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro API ao salvar message_id: {e}")
    
    async def _get_panel_message(self, guild: discord.Guild, panel_id: str, channel_id: int):
        """Busca mensagem do painel (cache ou API)"""
        
        if panel_id in self._panel_messages:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    return await channel.fetch_message(self._panel_messages[panel_id])
                except discord.NotFound:
                    del self._panel_messages[panel_id]
        
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild.id}/tickets/panels/{panel_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg_id = data.get("message_id")
                        if msg_id:
                            self._panel_messages[panel_id] = int(msg_id)
                            channel = guild.get_channel(channel_id)
                            if channel:
                                try:
                                    return await channel.fetch_message(int(msg_id))
                                except discord.NotFound:
                                    pass
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro ao buscar painel: {e}")
        
        return None
    
    # ═══════════════ PANEL CREATED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_created(self, guild: discord.Guild, event):
        """Cria embed do painel no Discord e salva message_id na API"""
        
        logger.info(f"🎨 Criando painel: guild={guild.id} panel={event.panel_id}")
        
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            logger.error(f"Canal {event.channel_id} não encontrado")
            return
        
        embed = discord.Embed(
            title=event.title,
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        view = TicketView(
            panel_id=event.panel_id,
            label=event.button_label or "Abrir Ticket",
            color=event.button_color or "blue"
        )
        
        message = await channel.send(embed=embed, view=view)
        logger.info(f"✅ Painel enviado: msg_id={message.id} channel={channel.id}")
        
        await self._save_panel_message_id(guild.id, event.panel_id, message.id)
    
    # ═══════════════ PANEL UPDATED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_updated(self, guild: discord.Guild, event):
        """Atualiza embed do painel existente"""
        
        logger.info(f"✏️ Atualizando painel: guild={guild.id} panel={event.panel_id}")
        
        message = await self._get_panel_message(guild, event.panel_id, int(event.channel_id))
        
        embed = discord.Embed(
            title=event.title,
            description=event.description or "Clique no botão abaixo para abrir um ticket.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
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
            logger.info(f"✅ Painel editado: msg_id={message.id}")
        else:
            channel = guild.get_channel(int(event.channel_id))
            if channel:
                message = await channel.send(embed=embed, view=view)
                await self._save_panel_message_id(guild.id, event.panel_id, message.id)
                logger.info(f"✅ Novo painel criado: msg_id={message.id}")
    
    # ═══════════════ PANEL DELETED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_panel_deleted(self, guild: discord.Guild, panel_id: str):
        """Remove mensagem do painel"""
        
        logger.info(f"🗑️ Removendo painel: guild={guild.id} panel={panel_id}")
        
        message_id = self._panel_messages.pop(panel_id, None)
        
        # Se não tem no cache, busca na API
        if not message_id:
            try:
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    url = f"{self.api_url}/guilds/{guild.id}/tickets/panels/{panel_id}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            message_id = data.get("message_id")
                            if message_id:
                                message_id = int(message_id)
            except aiohttp.ClientError as e:
                logger.error(f"❌ Erro ao buscar painel para deletar: {e}")
        
        if not message_id:
            logger.warning(f"⚠️ message_id não encontrado para o painel {panel_id}")
            return
        
        # Procura a mensagem em todos os canais
        for channel in guild.text_channels:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                logger.info(f"✅ Embed do painel removido: panel={panel_id} channel={channel.id}")
                return
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
            except Exception as e:
                logger.error(f"❌ Erro ao deletar mensagem no canal {channel.id}: {e}")
                continue
        
        logger.warning(f"⚠️ Mensagem {message_id} não encontrada em nenhum canal")
    
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
            try:
                user = await self.bot.fetch_user(int(event.user_id))
            except:
                user = None
        
        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"Olá {user.mention if user else 'usuário'}, um membro da equipe irá atendê-lo em breve.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📝 Ticket ID", value=event.ticket_id, inline=True)
        if user:
            embed.add_field(name="👤 Aberto por", value=user.mention, inline=True)
        embed.set_footer(text="Use os botões abaixo para gerenciar o ticket.")
        
        view = TicketControlView(ticket_id=event.ticket_id)
        
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Mensagem de boas-vindas enviada em {channel.id}")
    
    # ═══════════════ TICKET CLOSED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_closed(self, guild: discord.Guild, event):
        """Processa fechamento de ticket"""
        logger.info(f"🔒 Ticket fechado: guild={guild.id} ticket={event.ticket_id}")
    
    # ═══════════════ TICKET CLAIMED ═══════════════
    
    @commands.Cog.listener()
    async def on_ticket_claimed(self, guild: discord.Guild, event):
        """Notifica que um staff reivindicou o ticket"""
        logger.info(f"👤 Ticket reivindicado: guild={guild.id} ticket={event.ticket_id}")
    
    # ═══════════════ BOTÕES INTERATIVOS ═══════════════
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Processa cliques nos botões"""
        
        if not interaction.data or "custom_id" not in interaction.data:
            return
        
        custom_id = interaction.data["custom_id"]
        
        if custom_id.startswith("ticket_open_"):
            panel_id = custom_id.replace("ticket_open_", "")
            
            try:
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    url = f"{self.api_url}/guilds/{interaction.guild.id}/tickets/open"
                    async with session.post(url, json={
                        "user_id": str(interaction.user.id),
                        "panel_id": panel_id
                    }) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            await interaction.response.send_message(
                                f"🎫 Ticket aberto! <#{data.get('channel_id')}>",
                                ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                f"❌ Erro ao abrir ticket.",
                                ephemeral=True
                            )
            except aiohttp.ClientError:
                await interaction.response.send_message(
                    "❌ Erro ao comunicar com o sistema de tickets.",
                    ephemeral=True
                )
        
        elif custom_id.startswith("ticket_close_"):
            ticket_id = custom_id.replace("ticket_close_", "")
            
            try:
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    url = f"{self.api_url}/guilds/{interaction.guild.id}/tickets/{ticket_id}/close"
                    async with session.post(url, json={
                        "closed_by": str(interaction.user.id)
                    }) as resp:
                        if resp.status == 200:
                            await interaction.response.send_message(
                                "🔒 Ticket fechado!", ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                "❌ Erro ao fechar ticket.", ephemeral=True
                            )
            except aiohttp.ClientError:
                await interaction.response.send_message(
                    "❌ Erro ao comunicar com o sistema de tickets.",
                    ephemeral=True
                )
        
        elif custom_id.startswith("ticket_claim_"):
            ticket_id = custom_id.replace("ticket_claim_", "")
            
            try:
                async with aiohttp.ClientSession(auth=self.auth) as session:
                    url = f"{self.api_url}/guilds/{interaction.guild.id}/tickets/{ticket_id}/claim"
                    async with session.put(url, json={
                        "staff_id": str(interaction.user.id)
                    }) as resp:
                        if resp.status == 200:
                            await interaction.response.send_message(
                                "👤 Ticket reivindicado!", ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                "❌ Erro ao reivindicar ticket.", ephemeral=True
                            )
            except aiohttp.ClientError:
                await interaction.response.send_message(
                    "❌ Erro ao comunicar com o sistema de tickets.",
                    ephemeral=True
                )

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))