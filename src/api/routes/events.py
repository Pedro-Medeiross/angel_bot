from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ═══════════════ SCHEMAS ═══════════════

class PanelCreatedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    panel_id: str
    title: str
    description: Optional[str] = ""
    button_label: str
    button_color: str
    channel_id: Union[str, int]
    category_id: Optional[Union[str, int]] = None
    support_roles: Optional[list] = None

class PanelUpdatedEvent(PanelCreatedEvent):
    is_active: Optional[bool] = True

class PanelDeletedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    panel_id: str

class TicketEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    channel_id: Union[str, int]

class TicketCreatedEvent(TicketEvent):
    user_id: Union[str, int]

class TicketClosedEvent(TicketEvent):
    closed_by: Union[str, int]
    reason: Optional[str] = None

class TicketClaimedEvent(TicketEvent):
    staff_id: Union[str, int]

# ═══════════════ HELPERS ═══════════════

async def _get_guild(request: Request):
    """Extrai guild_id do payload e retorna a guild"""
    data = await request.json()
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    return guild, data

# ═══════════════ ROTAS ═══════════════

@router.post("/panel/created")
async def panel_created(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 panel/created: guild={guild.id} panel={data.get('panel_id')}")
    
    event = PanelCreatedEvent(**data)
    bot = request.app.state.bot
    bot.dispatch("ticket_panel_created", guild, event)
    return {"status": "ok"}

@router.post("/panel/updated")
async def panel_updated(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 panel/updated: guild={guild.id} panel={data.get('panel_id')}")
    
    event = PanelUpdatedEvent(**data)
    request.app.state.bot.dispatch("ticket_panel_updated", guild, event)
    return {"status": "ok"}

@router.post("/panel/deleted")
async def panel_deleted(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 panel/deleted: guild={guild.id} panel={data.get('panel_id')}")
    
    event = PanelDeletedEvent(**data)
    request.app.state.bot.dispatch("ticket_panel_deleted", guild, event.panel_id)
    return {"status": "ok"}

@router.post("/ticket/created")
async def ticket_created(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 ticket/created: guild={guild.id} ticket={data.get('ticket_id')}")
    
    event = TicketCreatedEvent(**data)
    request.app.state.bot.dispatch("ticket_created", guild, event)
    return {"status": "ok"}

@router.post("/ticket/closed")
async def ticket_closed(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 ticket/closed: guild={guild.id} ticket={data.get('ticket_id')}")
    
    event = TicketClosedEvent(**data)
    request.app.state.bot.dispatch("ticket_closed", guild, event)
    return {"status": "ok"}

@router.post("/ticket/claimed")
async def ticket_claimed(request: Request):
    guild, data = await _get_guild(request)
    logger.info(f"📥 ticket/claimed: guild={guild.id} ticket={data.get('ticket_id')}")
    
    event = TicketClaimedEvent(**data)
    request.app.state.bot.dispatch("ticket_claimed", guild, event)
    return {"status": "ok"}