import discord
import asyncio
from discord.ext import commands, tasks
from discord.ui import View, Button
import aiohttp
from typing import Optional
import logging
from src.core.config import config

logger = logging.getLogger(__name__)

class Tickets(commands.Cog):
    """Sistema de tickets"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self._panel_messages = {}
        self._staff_roles_cache = {}
        self.auto_close_inactive.start()
        logger.info(f"🔧 Tickets inicializado: api_url={self.api_url}")
    
    # ═══════════════ API HELPERS ═══════════════
    
    async def _api_get(self, path: str) -> Optional[dict | list]:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.get(f"{self.api_url}{path}") as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API GET {path}: {e}")
        return None
    
    async def _api_post(self, path: str, json: dict) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(f"{self.api_url}{path}", json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API POST {path}: {e}")
        return None
    
    async def _api_put(self, path: str, json: dict) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.put(f"{self.api_url}{path}", json=json) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"❌ API PUT {path}: {e}")
        return None
    
    # ═══════════════ TICKET HELPERS ═══════════════
    
    async def _get_staff_roles(self, guild_id: int) -> list:
        if guild_id in self._staff_roles_cache:
            return self._staff_roles_cache[guild_id]
        data = await self._api_get(f"/guilds/{guild_id}/tickets/bot/staff-roles")
        roles = data if isinstance(data, list) else []
        self._staff_roles_cache[guild_id] = roles
        return roles
    
    async def _get_ticket_info(self, guild_id: int, ticket_id: str) -> Optional[dict]:
        return await self._api_get(f"/guilds/{guild_id}/tickets/bot/{ticket_id}")
    
    async def _get_categories(self, guild_id: int) -> list:
        data = await self._api_get(f"/guilds/{guild_id}/tickets/bot/categories")
        if isinstance(data, list):
            return [c for c in data if c.get("is_active", True)]
        return []
    
    async def _get_feedback_log_channel(self, guild_id: int) -> int | None:
        """Busca canal de log de feedback"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.api_url}/guilds/{guild_id}/log-channel/ticket_feedback"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("channel_id")
        except aiohttp.ClientError as e:
            print(f"❌ Erro ao consultar API: {e}")
        return None
    
    async def _check_can_close(self, interaction: discord.Interaction, ticket_info: dict) -> tuple[bool, str]:
        user = interaction.user
        if user.guild_permissions.administrator:
            return True, "admin"
        if str(user.id) == str(ticket_info.get("user_id")):
            config = await self._api_get(f"/guilds/{interaction.guild.id}/tickets/bot/config")
            allow_user_close = config.get("allow_user_close", True) if config else True
            if allow_user_close:
                return True, "owner"
            return False, "Apenas staff pode fechar tickets."
        claimed_by = ticket_info.get("claimed_by")
        if claimed_by and str(user.id) == str(claimed_by):
            return True, "claimed"
        return False, "Você não tem permissão para fechar este ticket."
    
    # ═══════════════ PERMISSIONS ═══════════════
    
    async def _apply_ticket_permissions(self, channel, guild, user, claimed_by=None):
        staff_roles = await self._get_staff_roles(guild.id)
        config = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
        allow_attachments = config.get("allow_attachments", True) if config else True
        
        base_perms = discord.PermissionOverwrite(
            read_messages=True, send_messages=True,
            attach_files=allow_attachments, embed_links=allow_attachments,
            add_reactions=True, read_message_history=True,
            use_external_emojis=True, use_external_stickers=True
        )
        
        overwrites = {}
        for target, perm in channel.overwrites.items():
            overwrites[target] = perm
        
        # User sempre tem acesso
        overwrites[user] = base_perms
        
        # Bot sempre tem acesso total
        overwrites[guild.me] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True,
            attach_files=True, embed_links=True, add_reactions=True
        )
        
        # @everyone sem acesso
        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
        
        if claimed_by:
            # ⭐ CLAIMADO: só fica can_view_all + admin + quem claimou + user
            for sr in staff_roles:
                role = guild.get_role(int(sr["role_id"]))
                if role and sr.get("can_view_all"):
                    overwrites[role] = base_perms
                elif role:
                    # Staff sem can_view_all → remove acesso
                    overwrites[role] = discord.PermissionOverwrite(read_messages=False, send_messages=False)
            
            for role in guild.roles:
                if role.permissions.administrator and role.name != "@everyone":
                    overwrites[role] = base_perms
            
            claimed_member = guild.get_member(int(claimed_by))
            if claimed_member:
                overwrites[claimed_member] = base_perms
        else:
            # ⭐ NÃO CLAIMADO: todos staff veem
            for sr in staff_roles:
                role = guild.get_role(int(sr["role_id"]))
                if role:
                    overwrites[role] = base_perms
            
            for role in guild.roles:
                if role.permissions.administrator and role.name != "@everyone":
                    overwrites[role] = base_perms
        
        await channel.edit(overwrites=overwrites)
    
    async def _apply_chat_lock(self, channel, guild, locked: bool = True):
        staff_roles = await self._get_staff_roles(guild.id)
        staff_role_ids = {int(sr["role_id"]) for sr in staff_roles}
        for role in guild.roles:
            if role.permissions.administrator:
                staff_role_ids.add(role.id)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, attach_files=True, embed_links=True, add_reactions=True)
        }
        
        for target, overwrite in channel.overwrites.items():
            if target == guild.default_role or target == guild.me:
                continue
            if isinstance(target, discord.Role):
                if target.id in staff_role_ids:
                    overwrites[target] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                else:
                    overwrites[target] = discord.PermissionOverwrite(read_messages=False, send_messages=False)
            elif isinstance(target, discord.Member):
                is_staff = target.guild_permissions.administrator
                if not is_staff:
                    for role in target.roles:
                        if role.id in staff_role_ids:
                            is_staff = True
                            break
                if is_staff:
                    overwrites[target] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                else:
                    overwrites[target] = discord.PermissionOverwrite(read_messages=True, send_messages=not locked)
        
        await channel.edit(overwrites=overwrites)
        logger.info(f"🔒 Chat {'bloqueado' if locked else 'liberado'} em {channel.name}")
    
    # ═══════════════ CREATE TICKET ═══════════════
    
    async def _create_ticket(self, interaction, panel_id, category_key, priority, subject, description):
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
                await interaction.followup.send(f"❌ Você já tem {open_count} ticket(s) aberto(s). Limite máximo: {max_open}.", ephemeral=True)
                return
        
        ticket_count = (config_data.get("ticket_counter", 0) + 1) if config_data else 1
        category_id = panel_data.get("category_id")
        category = guild.get_channel(int(category_id)) if category_id else None
        
        channel_name = f"ticket-{ticket_count:04d}-{user.name}"
        topic = f"Ticket #{ticket_count} de {user.name} | {subject} | priority:{priority}"
        
        try:
            channel = await guild.create_text_channel(name=channel_name, category=category, topic=topic, reason=f"Ticket aberto por {user.name}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Não tenho permissão para criar canais.", ephemeral=True)
            return
        
        result = await self._api_post(f"/guilds/{guild.id}/tickets/open", {
            "user_id": str(user.id), "channel_id": str(channel.id), "panel_id": panel_id,
            "subject": subject, "description": description, "category": category_key, "priority": priority
        })
        
        if not result:
            await channel.delete()
            await interaction.followup.send("❌ Erro ao registrar ticket.", ephemeral=True)
            return
        
        ticket_id = result.get("id")
        
        # Permissões iniciais
        staff_roles = await self._get_staff_roles(guild.id)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, attach_files=True, embed_links=True, add_reactions=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=False, attach_files=allow_attachments, embed_links=allow_attachments)
        }
        for sr in staff_roles:
            role = guild.get_role(int(sr["role_id"]))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role in guild.roles:
            if role.permissions.administrator and role.name != "@everyone":
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        await channel.edit(overwrites=overwrites)
        
        if category:
            await self._reorder_category(category)
        
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_count}",
            description=f"Olá {user.mention}, um membro da equipe irá atendê-lo em breve.\n\n**Assunto:** {subject}\n**Descrição:** {description}",
            color=discord.Color.green()
        )
        embed.add_field(name="📝 Ticket ID", value=ticket_id, inline=True)
        embed.add_field(name="👤 Aberto por", value=user.mention, inline=True)
        embed.add_field(name="📂 Categoria", value=category_key, inline=True)
        embed.set_footer(text="Aguarde um staff liberar o chat.")
        
        from .views import TicketControlView
        view = TicketControlView(ticket_id=ticket_id)
        await channel.send(embed=embed, view=view)
        
        link_view = View()
        link_view.add_item(Button(label="Ir para o Ticket", style=discord.ButtonStyle.link, url=channel.jump_url, emoji="🎫"))
        await interaction.followup.send(f"🎫 Ticket #{ticket_count} aberto!", view=link_view, ephemeral=True)
        logger.info(f"✅ Ticket criado: {channel.id} ticket_id={ticket_id} categoria={category_key}")
    
    # ═══════════════ CLOSE TICKET ═══════════════
    
    async def _close_ticket(self, interaction: discord.Interaction, ticket_id: str, reason: str, role: str = "claimed"):
        guild = interaction.guild
        user = interaction.user
        channel = interaction.channel
        
        # Bloqueia
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)}
        for target, overwrite in channel.overwrites.items():
            if target == guild.default_role:
                continue
            if isinstance(target, (discord.Member, discord.Role)):
                overwrites[target] = discord.PermissionOverwrite(read_messages=overwrite.read_messages if overwrite.read_messages is not None else None, send_messages=False)
        overwrites[guild.me] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        await channel.edit(overwrites=overwrites)
        
        # Mensagem de fechamento
        title = "🔒 Ticket Fechado pelo Usuário" if role == "owner" else "🔒 Ticket Fechado"
        description = f"O usuário {user.mention} fechou este ticket." if role == "owner" else f"Ticket fechado por {user.mention}"
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        embed.add_field(name="📝 Resolução", value=reason, inline=False)
        await channel.send(embed=embed)
        
        # ⭐ BUSCA TICKET INFO PRIMEIRO (precisa do opener_id)
        ticket_info = await self._get_ticket_info(guild.id, ticket_id)
        opener_id = ticket_info.get("user_id") if ticket_info else None
        
        # Embed de feedback para o usuário
        if opener_id:
            opener = guild.get_member(int(opener_id))
            if opener and not opener.bot:
                is_staff = opener.guild_permissions.administrator
                if not is_staff:
                    staff_roles = await self._get_staff_roles(guild.id)
                    for sr in staff_roles:
                        role = guild.get_role(int(sr["role_id"]))
                        if role and role in opener.roles:
                            is_staff = True
                            break
                
                if not is_staff:
                    from discord.ui import View, Button
                    feedback_embed = discord.Embed(
                        title="⭐ Como foi seu atendimento?",
                        description=f"Seu ticket foi fechado.\n**Motivo:** {reason}\n\nDeixe seu feedback para nos ajudar a melhorar!",
                        color=discord.Color.gold()
                    )
                    feedback_view = View(timeout=300)
                    feedback_view.add_item(Button(
                        label="Dar Feedback",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"ticket_feedback_{ticket_id}",
                        emoji="⭐"
                    ))
                    try:
                        await channel.send(content=opener.mention, embed=feedback_embed, view=feedback_view)
                    except:
                        pass
        
        # Transcript + API (usa ticket_info já buscado)
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
        
        transcript_url = None
        try:
            messages_data = []
            async for message in channel.history(oldest_first=True, limit=500):
                if message.author.bot and message.embeds:
                    continue
                messages_data.append({
                    "author_name": message.author.display_name, "author_username": message.author.name,
                    "author_id": str(message.author.id), "author_avatar": str(message.author.display_avatar.url),
                    "is_admin": message.author.guild_permissions.administrator if isinstance(message.author, discord.Member) else False,
                    "content": message.content,
                    "attachments": [{"url": a.url, "filename": a.filename, "content_type": a.content_type, "size": a.size, "is_image": a.content_type and "image" in a.content_type, "is_video": a.content_type and "video" in a.content_type} for a in message.attachments],
                    "stickers": [{"name": s.name, "url": str(s.url)} for s in message.stickers],
                    "embeds": [{"title": e.title, "description": e.description, "url": e.url, "image_url": str(e.image.url) if e.image else None, "thumbnail_url": str(e.thumbnail.url) if e.thumbnail else None} for e in message.embeds],
                    "timestamp": message.created_at.isoformat()
                })
            
            transcript_data = {
                "ticket_id": ticket_id, "ticket_number": ticket_number, "guild_id": str(guild.id),
                "guild_name": guild.name, "guild_icon": str(guild.icon.url) if guild.icon else None,
                "opened_by_name": opened_by_name, "opened_by_id": opened_by_id, "opened_at": opened_at,
                "closed_by_name": str(user), "closed_by_id": str(user.id),
                "close_reason": reason, "closed_at": discord.utils.utcnow().isoformat(), "messages": messages_data
            }
            
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(f"{self.api_url}/guilds/{guild.id}/tickets/{ticket_id}/transcript", json=transcript_data) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        transcript_url = data.get("url")
                        logger.info(f"📸 Transcript salvo: {transcript_url}")
        except Exception as e:
            logger.error(f"❌ Erro ao gerar/enviar transcript: {e}")
        
        await self._api_post(f"/guilds/{guild.id}/tickets/{ticket_id}/bot/close", {"closed_by": str(user.id), "reason": reason})
        
        if transcript_url:
            config_data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
            print(f'config data {config_data}')
            transcript_channel_id = config_data.get("transcript_channel") if config_data else None
            print(f'channel_id {transcript_channel_id}')
            if transcript_channel_id:
                transcript_channel = guild.get_channel(int(transcript_channel_id))
                if transcript_channel:
                    transcript_embed = discord.Embed(title="📋 Ticket Fechado", color=discord.Color.blue())
                    transcript_embed.add_field(name="📝 Nome do Ticket", value=f"ticket-{ticket_number}", inline=True)
                    transcript_embed.add_field(name="👤 Autor do Ticket", value=f"<@{opened_by_id}>", inline=True)
                    transcript_embed.add_field(name="🔒 Fechado por", value=user.mention, inline=True)
                    transcript_embed.add_field(name="📅 Data de Abertura", value=opened_at, inline=True)
                    transcript_embed.add_field(name="📅 Data de encerramento", value=discord.utils.utcnow().strftime("%d/%m/%Y %H:%M"), inline=True)
                    transcript_embed.add_field(name="📝 Motivo", value=reason, inline=False)
                    
                    link_view = View()
                    link_view.add_item(Button(label="Ver Transcrição", style=discord.ButtonStyle.link, url=transcript_url, emoji="📄"))
                    await transcript_channel.send(embed=transcript_embed, view=link_view)
                    logger.info(f"📋 Transcript enviado em {transcript_channel.id}")
        
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket fechado por {user.name}")
            logger.info(f"🗑️ Canal deletado: {channel.id} ticket={ticket_id}")
        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para deletar canal: {channel.id}")
    
    # ═══════════════ PRIORITY & REORDER ═══════════════
    
    async def _change_priority(self, interaction, ticket_id, priority):
        await interaction.response.defer(ephemeral=True)
        valid = ["urgent", "high", "medium", "low"]
        if priority not in valid:
            await interaction.followup.send(f"❌ Prioridade inválida.", ephemeral=True)
            return
        await self._api_put(f"/guilds/{interaction.guild.id}/tickets/{ticket_id}/bot/priority", {"priority": priority})
        if interaction.channel.category:
            await self._reorder_category(interaction.channel.category)
        await interaction.followup.send(f"✅ Prioridade alterada para **{priority.upper()}**", ephemeral=True)
    
    async def _reorder_category(self, category):
        if not category:
            return
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        channels = [ch for ch in category.channels]
        
        def get_priority(ch):
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
    
    # ═══════════════ PANEL MESSAGE ═══════════════
    
    async def _save_panel_message_id(self, guild_id: int, panel_id: str, message_id: int):
        result = await self._api_put(f"/guilds/{guild_id}/tickets/panels/{panel_id}/message", {"message_id": message_id})
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
    
    # ═══════════════ AUTO CLOSE ═══════════════
    
    @tasks.loop(minutes=10)
    async def auto_close_inactive(self):
        from datetime import datetime, timezone
        
        for guild in self.bot.guilds:
            config = await self._api_get(f"/guilds/{guild.id}/tickets/bot/config")
            if not config:
                continue
            auto_close_hours = config.get("auto_close_hours", 0)
            if auto_close_hours <= 0:
                continue
            
            all_tickets = []
            for status in ["open", "claimed"]:
                data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/list?status={status}")
                if data:
                    all_tickets.extend(data.get("tickets", []))
            
            now = datetime.now(timezone.utc)
            
            for ticket in all_tickets:
                try:
                    channel = guild.get_channel(int(ticket["channel_id"]))
                    if not channel:
                        continue
                    last_msg = None
                    async for msg in channel.history(limit=1):
                        last_msg = msg
                        break
                    if not last_msg:
                        continue
                    
                    hours_inactive = (now - last_msg.created_at).total_seconds() / 3600
                    if hours_inactive < auto_close_hours:
                        continue
                    
                    # Transcript
                    messages_data = []
                    async for message in channel.history(oldest_first=True, limit=500):
                        if message.author.bot and message.embeds:
                            continue
                        messages_data.append({
                            "author_name": message.author.display_name, "author_username": message.author.name,
                            "author_id": str(message.author.id), "author_avatar": str(message.author.display_avatar.url),
                            "content": message.content,
                            "attachments": [{"url": a.url, "filename": a.filename, "content_type": a.content_type, "size": a.size} for a in message.attachments],
                            "stickers": [{"name": s.name, "url": str(s.url)} for s in message.stickers],
                            "embeds": [{"title": e.title, "description": e.description, "url": e.url} for e in message.embeds],
                            "timestamp": message.created_at.isoformat()
                        })
                    
                    transcript_data = {
                        "ticket_id": ticket["id"], "ticket_number": ticket.get("ticket_number", ""),
                        "guild_id": str(guild.id), "guild_name": guild.name,
                        "guild_icon": str(guild.icon.url) if guild.icon else None,
                        "opened_by_name": ticket.get("user_name", "Desconhecido"),
                        "opened_by_id": str(ticket.get("user_id", "")),
                        "opened_at": ticket.get("created_at", ""),
                        "closed_by_name": str(self.bot.user), "closed_by_id": str(self.bot.user.id),
                        "close_reason": f"Fechado automaticamente por inatividade ({auto_close_hours}h)",
                        "closed_at": discord.utils.utcnow().isoformat(), "messages": messages_data
                    }
                    
                    async with aiohttp.ClientSession(auth=self.auth) as session:
                        await session.post(f"{self.api_url}/guilds/{guild.id}/tickets/{ticket['id']}/transcript", json=transcript_data)
                    
                    await self._api_post(f"/guilds/{guild.id}/tickets/{ticket['id']}/bot/close", {"closed_by": str(self.bot.user.id), "reason": f"Fechado automaticamente por inatividade ({auto_close_hours}h)"})
                    
                    await channel.set_permissions(guild.default_role, send_messages=False)
                    await channel.set_permissions(guild.me, send_messages=True)
                    
                    embed = discord.Embed(title="⏰ Ticket Fechado por Inatividade", description=f"Ticket fechado automaticamente após {auto_close_hours}h sem mensagens.", color=discord.Color.orange())
                    await channel.send(embed=embed)
                    
                    await asyncio.sleep(5)
                    try:
                        await channel.delete()
                    except:
                        pass
                    logger.info(f"⏰ Ticket {ticket['id']} fechado por inatividade em {guild.name}")
                except Exception:
                    continue
    
    @auto_close_inactive.before_loop
    async def before_auto_close(self):
        await self.bot.wait_until_ready()
    
    def cog_unload(self):
        self.auto_close_inactive.cancel()
    
    # ═══════════════ LISTENERS ═══════════════
    
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.bot.is_ready():
            return
        total_registered = 0
        for guild in self.bot.guilds:
            try:
                data = await self._api_get(f"/guilds/{guild.id}/tickets/bot/list?status=open&limit=500")
                if not data:
                    continue
                for ticket in data.get("tickets", []):
                    ticket_id = ticket.get("id")
                    claimed_by = ticket.get("claimed_by")
                    if ticket_id:
                        from .views import TicketControlView
                        self.bot.add_view(TicketControlView(ticket_id, claimed=(claimed_by is not None)))
                        total_registered += 1
            except Exception as e:
                logger.error(f"❌ Erro ao registrar views em {guild.name}: {e}")
        logger.info(f"✅ {total_registered} views de tickets abertos registradas")
    
    @commands.Cog.listener()
    async def on_ticket_panel_created(self, guild: discord.Guild, event):
        channel = guild.get_channel(int(event.channel_id))
        if not channel:
            return
        from .views import TicketView
        embed = discord.Embed(title=event.title, description=event.description or "Clique no botão abaixo para abrir um ticket.", color=discord.Color.blue())
        view = TicketView(panel_id=event.panel_id, label=event.button_label or "Abrir Ticket", color=event.button_color or "blue")
        message = await channel.send(embed=embed, view=view)
        await self._save_panel_message_id(guild.id, event.panel_id, message.id)
    
    @commands.Cog.listener()
    async def on_ticket_panel_updated(self, guild: discord.Guild, event):
        message = await self._get_panel_message(guild, event.panel_id, int(event.channel_id))
        from .views import TicketView
        embed = discord.Embed(title=event.title, description=event.description or "Clique no botão abaixo para abrir um ticket.", color=discord.Color.blue())
        if event.is_active is False:
            embed.description = "🚫 Este painel foi desativado."
            view = None
        else:
            view = TicketView(panel_id=event.panel_id, label=event.button_label or "Abrir Ticket", color=event.button_color or "blue")
        if message:
            await message.edit(embed=embed, view=view)
        else:
            channel = guild.get_channel(int(event.channel_id))
            if channel:
                message = await channel.send(embed=embed, view=view)
                await self._save_panel_message_id(guild.id, event.panel_id, message.id)
    
    @commands.Cog.listener()
    async def on_ticket_panel_deleted(self, guild: discord.Guild, panel_id: str):
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
    
    @commands.Cog.listener()
    async def on_ticket_claimed(self, guild: discord.Guild, event):
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
                await self._apply_ticket_permissions(channel, guild, user, claimed_by=str(event.staff_id))
                await channel.set_permissions(user, send_messages=True)
        embed = discord.Embed(title="👤 Ticket Atendido", description=f"{staff.mention} está atendendo este ticket.\n🔓 Chat liberado automaticamente.", color=discord.Color.blue())
        await channel.send(embed=embed)
    
    # ═══════════════ INTERACTIONS ═══════════════
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        from .handlers import handle_interaction
        await handle_interaction(self, interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))