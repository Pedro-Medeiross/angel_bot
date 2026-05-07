from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ═══════════════ SCHEMAS ═══════════════

class PanelEvent(BaseModel):
    guild_id: int
    panel_id: str
    title: str
    description: Optional[str] = ""
    button_label: str
    button_color: str
    category_id: Optional[str] = None
    support_roles: List[str] = []
    is_active: Optional[bool] = True

class PanelDeletedEvent(BaseModel):
    guild_id: int
    panel_id: str

class TicketCreatedEvent(BaseModel):
    guild_id: int
    ticket_id: str
    channel_id: str
    user_id: str

class TicketClosedEvent(BaseModel):
    guild_id: int
    ticket_id: str
    closed_by: str
    reason: Optional[str] = None

class TicketClaimedEvent(BaseModel):
    guild_id: int
    ticket_id: str
    staff_id: str

# ═══════════════ ROTAS ═══════════════

@router.post("/panel/created")
async def panel_created(event: PanelEvent, request: Request):
    """API notificou que um painel de ticket foi criado"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento panel/created: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    # Dispara evento interno para a cog de tickets processar
    bot.dispatch("ticket_panel_created", guild, event)
    return {"status": "ok"}

@router.post("/panel/updated")
async def panel_updated(event: PanelEvent, request: Request):
    """API notificou que um painel foi atualizado"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento panel/updated: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_panel_updated", guild, event)
    return {"status": "ok"}

@router.post("/panel/deleted")
async def panel_deleted(event: PanelDeletedEvent, request: Request):
    """API notificou que um painel foi deletado"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento panel/deleted: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_panel_deleted", guild, event.panel_id)
    return {"status": "ok"}

@router.post("/ticket/created")
async def ticket_created(event: TicketCreatedEvent, request: Request):
    """API notificou que um ticket foi aberto"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento ticket/created: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_created", guild, event)
    return {"status": "ok"}

@router.post("/ticket/closed")
async def ticket_closed(event: TicketClosedEvent, request: Request):
    """API notificou que um ticket foi fechado"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento ticket/closed: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_closed", guild, event)
    return {"status": "ok"}

@router.post("/ticket/claimed")
async def ticket_claimed(event: TicketClaimedEvent, request: Request):
    """API notificou que um ticket foi reinvindicado"""
    bot = request.app.state.bot
    logger.info(f"📥 Evento ticket/claimed: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_claimed", guild, event)
    return {"status": "ok"}