import discord
from discord.ext import commands
import aiohttp
from src.core.config import config
from src.utils.log_api import log_api

class MessageLogs(commands.Cog):
    """Logs de eventos de mensagem"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = config.API_URL
        self.api_user = config.API_USER
        self.api_pass = config.API_PASS
        self.auth = aiohttp.BasicAuth(self.api_user, self.api_pass)
        self.log_api = log_api
    
    async def get_log_channel(self, guild_id: int, log_type: str) -> int | None:
        """Pergunta pra API qual canal usar para esse tipo de log"""
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
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log de mensagem deletada"""
        
        if message.author.bot or not message.guild:
            return
        
        # Verifica se é imagem
        has_image = any(
            a.content_type and "image" in a.content_type 
            for a in message.attachments
        )
        
        # 1️⃣ Log principal: message_delete
        log_channel_id = await self.get_log_channel(message.guild.id, "message_delete")
        
        if log_channel_id:
            log_channel = message.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Mensagem deletada",
                    description=f"{message.author.mention} em {message.channel.mention}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                embed.set_footer(text=f"ID: {message.author.id}")
                
                if message.content:
                    embed.add_field(name="💬 Conteúdo", value=message.content[:1024], inline=False)
                
                if message.attachments:
                    attachments = "\n".join([a.url for a in message.attachments])
                    embed.add_field(name="📎 Anexos", value=attachments[:1024], inline=False)
                
                await log_channel.send(embed=embed)
        
        # Envia log pra API
        await self.log_api.send_log(
            guild_id=message.guild.id,
            log_type="message_delete",
            user_id=message.author.id,
            channel_id=message.channel.id,
            data={
                "message_id": str(message.id),
                "content": message.content,
                "author_name": str(message.author),
                "author_avatar": str(message.author.display_avatar.url),
                "channel_name": message.channel.name,
                "channel_id": str(message.channel.id),
                "attachments": [a.url for a in message.attachments],
                "message_created_at": message.created_at.isoformat()
            }
        )
        
        # 2️⃣ Se tinha imagem: image_delete
        if has_image:
            image_channel_id = await self.get_log_channel(message.guild.id, "image_delete")
            
            if image_channel_id:
                image_channel = message.guild.get_channel(image_channel_id)
                if image_channel and image_channel != log_channel:  # Evita duplicar se for o mesmo canal
                    embed = discord.Embed(
                        title="🖼️ Imagem deletada",
                        description=f"{message.author.mention} em {message.channel.mention}",
                        color=discord.Color.purple(),
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                    
                    for att in message.attachments:
                        if att.content_type and "image" in att.content_type:
                            embed.set_image(url=att.url)
                            break
                    
                    await image_channel.send(embed=embed)
            
            # Envia log de imagem pra API
            await self.log_api.send_log(
                guild_id=message.guild.id,
                log_type="image_delete",
                user_id=message.author.id,
                channel_id=message.channel.id,
                data={
                    "message_id": str(message.id),
                    "author_name": str(message.author),
                    "channel_name": message.channel.name,
                    "channel_id": str(message.channel.id),
                    "images": [a.url for a in message.attachments if a.content_type and "image" in a.content_type]
                }
            )
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log de mensagem editada"""
        
        if before.author.bot or not before.guild:
            return
        
        # Ignora se o conteúdo não mudou (embed, link preview)
        if before.content == after.content:
            return
        
        log_channel_id = await self.get_log_channel(before.guild.id, "message_edit")
        
        if log_channel_id:
            log_channel = before.guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="✏️ Mensagem editada",
                    description=f"{before.author.mention} em {before.channel.mention}",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
                embed.set_footer(text=f"ID: {before.author.id}")
                
                embed.add_field(name="❌ Antes", value=before.content[:1024] or "*vazio*", inline=False)
                embed.add_field(name="✅ Depois", value=after.content[:1024] or "*vazio*", inline=False)
                embed.add_field(name="🔗 Link", value=f"[Ir para mensagem]({after.jump_url})", inline=False)
                
                await log_channel.send(embed=embed)
        
        # Envia log pra API
        await self.log_api.send_log(
            guild_id=before.guild.id,
            log_type="message_edit",
            user_id=before.author.id,
            channel_id=before.channel.id,
            data={
                "message_id": str(after.id),
                "old_content": before.content,
                "new_content": after.content,
                "author_name": str(before.author),
                "author_avatar": str(before.author.display_avatar.url),
                "channel_name": before.channel.name,
                "channel_id": str(before.channel.id),
                "jump_url": after.jump_url
            }
        )
        
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        """Log de mensagens deletadas em massa"""
        
        if not messages:
            return
        
        guild = messages[0].guild
        if not guild:
            return
        
        channel = messages[0].channel
        
        log_channel_id = await self.get_log_channel(guild.id, "bulk_message_delete")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🗑️ Mensagens deletadas em massa",
                    description=f"{len(messages)} mensagens em {channel.mention}",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Lista as últimas 10 mensagens no embed
                msg_list = []
                for msg in messages[:10]:
                    author = str(msg.author)
                    content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                    msg_list.append(f"**{author}**: {content or '*sem texto*'}")
                
                embed.add_field(
                    name="📝 Últimas mensagens",
                    value="\n".join(msg_list) or "*mensagens vazias*",
                    inline=False
                )
                
                if len(messages) > 10:
                    embed.set_footer(text=f"Mostrando 10 de {len(messages)} mensagens")
                
                await log_channel.send(embed=embed)
        
        # Envia log pra API
        await self.log_api.send_log(
            guild_id=guild.id,
            log_type="bulk_message_delete",
            channel_id=channel.id,
            data={
                "count": len(messages),
                "channel_name": channel.name,
                "channel_id": str(channel.id),
                "messages": [
                    {
                        "message_id": str(msg.id),
                        "author_name": str(msg.author),
                        "author_id": str(msg.author.id),
                        "content": msg.content
                    }
                    for msg in messages
                ]
            }
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogs(bot))