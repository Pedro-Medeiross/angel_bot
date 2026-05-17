import discord
from discord.ext import commands
from io import StringIO
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class MessageLogs(commands.Cog):
    """Logs de eventos de mensagem"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
        self.log_api = log_api
    
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
    
    def _build_message_embed(self, author: discord.Member | discord.User, channel: discord.TextChannel,
                             title: str, color: discord.Color) -> discord.Embed:
        """Cria embed base para logs de mensagem"""
        embed = discord.Embed(
            title=title,
            description=f"{author.mention} em {channel.mention}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        embed.set_footer(text=f"ID: {author.id} | @{author.name}")
        return embed
    
    def _build_author_data(self, author: discord.Member | discord.User) -> dict:
        """Dados base do autor para API"""
        return {
            "user_name": author.name,
            "display_name": author.display_name,
            "user_avatar": str(author.display_avatar.url),
        }
    
    @staticmethod
    def _format_whatsapp_style(messages: list[discord.Message]) -> str:
        """Formata mensagens estilo WhatsApp export"""
        lines = []
        for msg in sorted(messages, key=lambda m: m.created_at):
            timestamp = msg.created_at.strftime("%d/%m/%Y %H:%M")
            author = msg.author.display_name or msg.author.name
            content = msg.content or "*sem texto*"
            lines.append(f"[{timestamp}] {author} (@{msg.author.name}): {content}")
            for att in msg.attachments:
                lines.append(f"  📎 {att.url}")
        return "\n".join(lines)
    
    @staticmethod
    def _has_image(message: discord.Message) -> bool:
        """Verifica se a mensagem tem anexo de imagem"""
        return any(a.content_type and "image" in a.content_type for a in message.attachments)
    
    # ═══════════════ MESSAGE DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        has_image = self._has_image(message)
        log_channel_id = await self._get_log_channel(message.guild.id, "message_delete")
        
        if log_channel_id:
            log_channel = message.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_message_embed(message.author, message.channel, "🗑️ Mensagem deletada", discord.Color.red())
                
                if message.content and len(message.content) > 1024:
                    txt_file = discord.File(StringIO(message.content), filename=f"deleted_{message.id}.txt")
                    embed.add_field(name="💬 Conteúdo", value="*Mensagem longa, veja o arquivo anexo*", inline=False)
                    if message.attachments:
                        embed.add_field(name="📎 Anexos", value="\n".join(a.url for a in message.attachments)[:1024], inline=False)
                    await log_channel.send(embed=embed, file=txt_file)
                else:
                    if message.content:
                        embed.add_field(name="💬 Conteúdo", value=message.content or "*vazio*", inline=False)
                    if message.attachments:
                        embed.add_field(name="📎 Anexos", value="\n".join(a.url for a in message.attachments)[:1024], inline=False)
                    await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=message.guild.id, log_type="message_delete",
            user_id=message.author.id, channel_id=message.channel.id,
            data={
                "message_id": str(message.id), "content": message.content,
                **self._build_author_data(message.author),
                "channel_name": message.channel.name, "channel_id": str(message.channel.id),
                "attachments": [a.url for a in message.attachments],
                "message_created_at": message.created_at.isoformat()
            }
        )
        
        if has_image:
            await self._log_image_delete(message, log_channel_id)
    
    async def _log_image_delete(self, message: discord.Message, exclude_channel_id: int = None):
        image_channel_id = await self._get_log_channel(message.guild.id, "image_delete")
        
        if image_channel_id and image_channel_id != exclude_channel_id:
            image_channel = message.guild.get_channel(image_channel_id)
            if image_channel:
                embed = self._build_message_embed(message.author, message.channel, "🖼️ Imagem deletada", discord.Color.purple())
                for att in message.attachments:
                    if att.content_type and "image" in att.content_type:
                        embed.set_image(url=att.url)
                        break
                await image_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=message.guild.id, log_type="image_delete",
            user_id=message.author.id, channel_id=message.channel.id,
            data={
                "message_id": str(message.id),
                **self._build_author_data(message.author),
                "channel_name": message.channel.name, "channel_id": str(message.channel.id),
                "images": [a.url for a in message.attachments if a.content_type and "image" in a.content_type]
            }
        )
    
    # ═══════════════ MESSAGE EDIT ═══════════════
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        log_channel_id = await self._get_log_channel(before.guild.id, "message_edit")
        
        if log_channel_id:
            log_channel = before.guild.get_channel(log_channel_id)
            if log_channel:
                embed = self._build_message_embed(before.author, before.channel, "✏️ Mensagem editada", discord.Color.orange())
                embed.add_field(name="🔗 Link", value=f"[Ir para mensagem]({after.jump_url})", inline=False)
                
                content_long = len(before.content) > 1024 or len(after.content) > 1024
                
                if content_long:
                    txt_content = f"=== ANTES ===\n{before.content or '*vazio*'}\n\n=== DEPOIS ===\n{after.content or '*vazio*'}"
                    txt_file = discord.File(StringIO(txt_content), filename=f"edited_{after.id}.txt")
                    embed.add_field(name="📝 Conteúdo", value="*Mensagem longa, veja o arquivo anexo*", inline=False)
                    await log_channel.send(embed=embed, file=txt_file)
                else:
                    embed.add_field(name="❌ Antes", value=before.content[:1024] or "*vazio*", inline=False)
                    embed.add_field(name="✅ Depois", value=after.content[:1024] or "*vazio*", inline=False)
                    await log_channel.send(embed=embed)
        
        await self.log_api.send_log(
            guild_id=before.guild.id, log_type="message_edit",
            user_id=before.author.id, channel_id=before.channel.id,
            data={
                "message_id": str(after.id), "old_content": before.content, "new_content": after.content,
                **self._build_author_data(before.author),
                "channel_name": before.channel.name, "channel_id": str(before.channel.id),
                "jump_url": after.jump_url
            }
        )
    
    # ═══════════════ BULK DELETE ═══════════════
    
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        if not messages:
            return
        
        guild = messages[0].guild
        channel = messages[0].channel
        if not guild:
            return
        
        log_channel_id = await self._get_log_channel(guild.id, "bulk_message_delete")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                txt_content = self._format_whatsapp_style(messages)
                txt_file = discord.File(
                    StringIO(txt_content),
                    filename=f"bulk_delete_{channel.name}_{discord.utils.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                
                embed = discord.Embed(
                    title="🗑️ Mensagens deletadas em massa",
                    description=f"{len(messages)} mensagens em {channel.mention}",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow()
                )
                
                msg_list = [
                    f"**{msg.author.display_name}**: {msg.content[:50]}{'...' if len(msg.content) > 50 else '' or '*sem texto*'}"
                    for msg in messages[:5]
                ]
                
                embed.add_field(name="📝 Resumo", value="\n".join(msg_list) or "*mensagens vazias*", inline=False)
                if len(messages) > 5:
                    embed.set_footer(text=f"Mostrando 5 de {len(messages)} mensagens. Detalhes no arquivo.")
                
                await log_channel.send(embed=embed, file=txt_file)
        
        await self.log_api.send_log(
            guild_id=guild.id, log_type="bulk_message_delete", channel_id=channel.id,
            data={
                "count": len(messages), "channel_name": channel.name, "channel_id": str(channel.id),
                "messages": [
                    {
                        "message_id": str(msg.id),
                        "user_name": msg.author.name,
                        "display_name": msg.author.display_name,
                        "content": msg.content,
                        "attachments": [a.url for a in msg.attachments],
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogs(bot))