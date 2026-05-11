import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import discord

TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            width: 800px;
        }}
        .header {{
            background: #181825;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            text-align: center;
            border: 1px solid #313244;
        }}
        .header .server-icon {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            margin-bottom: 10px;
        }}
        .header h1 {{ font-size: 22px; color: #cdd6f4; margin-bottom: 5px; }}
        .header .subtitle {{ font-size: 13px; color: #a6adc8; }}
        .info {{
            background: #181825;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #313244;
        }}
        .info-row {{ display: flex; justify-content: space-between; font-size: 13px; color: #a6adc8; margin-bottom: 5px; }}
        .info-row span {{ color: #cdd6f4; }}
        .messages {{ margin-bottom: 15px; }}
        .message {{
            display: flex;
            margin-bottom: 12px;
            padding: 10px;
            background: #181825;
            border-radius: 8px;
            border: 1px solid #313244;
        }}
        .message .avatar {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            margin-right: 12px;
            flex-shrink: 0;
        }}
        .message .content {{ flex: 1; }}
        .message .author {{
            font-weight: 600;
            color: #cdd6f4;
            font-size: 14px;
            margin-bottom: 2px;
        }}
        .message .badge {{
            font-size: 10px;
            background: #f38ba8;
            color: #1e1e2e;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 5px;
            font-weight: 700;
        }}
        .message .timestamp {{
            font-size: 11px;
            color: #6c7086;
            margin-bottom: 4px;
        }}
        .message .text {{
            font-size: 13px;
            color: #bac2de;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .message .attachment {{
            font-size: 12px;
            color: #89b4fa;
            margin-top: 4px;
        }}
        .footer {{
            background: #181825;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid #313244;
        }}
        .footer p {{ font-size: 13px; color: #a6adc8; margin-bottom: 3px; }}
        .footer span {{ color: #cdd6f4; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="header">
        {server_icon}
        <h1>{server_name}</h1>
        <p class="subtitle">Transcript do Ticket</p>
    </div>
    <div class="info">
        <div class="info-row">📝 <span>{ticket_title}</span></div>
        <div class="info-row">👤 Aberto por: <span>{opened_by}</span></div>
        <div class="info-row">📅 Data de abertura: <span>{opened_at}</span></div>
    </div>
    <div class="messages">
        {messages_html}
    </div>
    <div class="footer">
        <p>🔒 Fechado por: <span>{closed_by}</span></p>
        <p>📝 Motivo: <span>{close_reason}</span></p>
        <p>📅 Transcript gerado em: <span>{generated_at}</span></p>
    </div>
</body>
</html>"""

async def generate_transcript(
    channel: discord.TextChannel,
    ticket_title: str,
    opened_by: str,
    opened_at: str,
    closed_by: str,
    close_reason: str
) -> bytes:
    """Gera uma imagem PNG do transcript do ticket"""
    
    messages_html = ""
    async for message in channel.history(oldest_first=True, limit=500):
        if message.author.bot and message.embeds:
            continue
        
        timestamp = message.created_at.strftime("%d/%m/%Y %H:%M")
        author_name = message.author.display_name
        avatar_url = str(message.author.display_avatar.url)
        content = message.content or ""
        
        badge = ""
        if isinstance(message.author, discord.Member):
            if message.author.guild_permissions.administrator:
                badge = '<span class="badge">ADMIN</span>'
            elif any(r.name.lower() in ["staff", "moderador", "mod", "suporte"] for r in message.author.roles):
                badge = '<span class="badge">STAFF</span>'
        
        attachments_html = ""
        for att in message.attachments:
            attachments_html += f'<div class="attachment">📎 <a href="{att.url}" style="color:#89b4fa">{att.filename}</a></div>'
        
        messages_html += f"""
        <div class="message">
            <img class="avatar" src="{avatar_url}" alt="avatar">
            <div class="content">
                <div class="author">{author_name}{badge}</div>
                <div class="timestamp">{timestamp}</div>
                <div class="text">{content}</div>
                {attachments_html}
            </div>
        </div>
        """
    
    server_icon_html = ""
    if channel.guild.icon:
        server_icon_html = f'<img class="server-icon" src="{channel.guild.icon.url}" alt="Server Icon">'
    
    html = TEMPLATE.format(
        server_icon=server_icon_html,
        server_name=channel.guild.name,
        ticket_title=ticket_title,
        opened_by=opened_by,
        opened_at=opened_at,
        messages_html=messages_html,
        closed_by=closed_by,
        close_reason=close_reason,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    )
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 800, "height": 600})
        await page.set_content(html)
        
        height = await page.evaluate("document.body.scrollHeight")
        await page.set_viewport_size({"width": 800, "height": height + 20})
        
        screenshot = await page.screenshot(full_page=True, type="png")
        await browser.close()
        
        return screenshot