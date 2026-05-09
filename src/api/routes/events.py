from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
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
    
    @field_validator('channel_id', mode='before')
    @classmethod
    def coerce_channel_id(cls, v):
        return str(v)
    
    @field_validator('category_id', mode='before')
    @classmethod
    def coerce_category_id(cls, v):
        return str(v) if v is not None else None

class PanelUpdatedEvent(BaseModel):
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
    is_active: Optional[bool] = True
    
    @field_validator('channel_id', mode='before')
    @classmethod
    def coerce_channel_id(cls, v):
        return str(v)
    
    @field_validator('category_id', mode='before')
    @classmethod
    def coerce_category_id(cls, v):
        return str(v) if v is not None else None

class PanelDeletedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    panel_id: str

class TicketCreatedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    channel_id: Union[str, int]
    user_id: Union[str, int]
    
    @field_validator('channel_id', 'user_id', mode='before')
    @classmethod
    def coerce_to_str(cls, v):
        return str(v)

class TicketClosedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    closed_by: Union[str, int]
    reason: Optional[str] = None
    
    @field_validator('closed_by', mode='before')
    @classmethod
    def coerce_closed_by(cls, v):
        return str(v)

class TicketClaimedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    staff_id: Union[str, int]
    
    @field_validator('staff_id', mode='before')
    @classmethod
    def coerce_staff_id(cls, v):
        return str(v)

# ═══════════════ ROTAS ═══════════════

@router.post("/panel/created")
async def panel_created(event: PanelCreatedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 panel/created: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_panel_created", guild, event)
    return {"status": "ok"}

@router.post("/panel/updated")
async def panel_updated(event: PanelUpdatedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 panel/updated: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_panel_updated", guild, event)
    return {"status": "ok"}

@router.post("/panel/deleted")
async def panel_deleted(event: PanelDeletedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 panel/deleted: guild={event.guild_id} panel={event.panel_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_panel_deleted", guild, event.panel_id)
    return {"status": "ok"}

@router.post("/ticket/created")
async def ticket_created(event: TicketCreatedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 ticket/created: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_created", guild, event)
    return {"status": "ok"}

@router.post("/ticket/closed")
async def ticket_closed(event: TicketClosedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 ticket/closed: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_closed", guild, event)
    return {"status": "ok"}

@router.post("/ticket/claimed")
async def ticket_claimed(event: TicketClaimedEvent, request: Request):
    bot = request.app.state.bot
    logger.info(f"📥 ticket/claimed: guild={event.guild_id} ticket={event.ticket_id}")
    
    guild = bot.get_guild(event.guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    bot.dispatch("ticket_claimed", guild, event)
    return {"status": "ok"}