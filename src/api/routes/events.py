from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, Dict
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
    channel_id: Any  # Aceita qualquer tipo
    category_id: Optional[Any] = None  # Aceita qualquer tipo
    support_roles: Optional[Any] = None

class PanelUpdatedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    guild_id: int
    panel_id: str
    title: str
    description: Optional[str] = ""
    button_label: str
    button_color: str
    channel_id: Any
    category_id: Optional[Any] = None
    support_roles: Optional[Any] = None
    is_active: Optional[bool] = True

class PanelDeletedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    panel_id: str

class TicketCreatedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    channel_id: Any
    user_id: Any

class TicketClosedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    closed_by: Any
    reason: Optional[str] = None

class TicketClaimedEvent(BaseModel):
    model_config = ConfigDict(extra='allow')
    guild_id: int
    ticket_id: str
    staff_id: Any

# ═══════════════ ROTAS ═══════════════

@router.post("/panel/created")
async def panel_created(request: Request):
    data = await request.json()
    logger.info(f"📥 panel/created FULL PAYLOAD: {json.dumps(data, indent=2)}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    # Mapeia o campo correto (tenta channel_id, senão procura no payload)
    channel_id = data.get("channel_id") or data.get("text_channel_id") or data.get("target_channel_id")
    if not channel_id:
        logger.error(f"❌ Não encontrei channel_id no payload: {list(data.keys())}")
        raise HTTPException(status_code=400, detail="Missing channel_id")
    
    # Cria objeto com os dados
    event_data = {
        "guild_id": data["guild_id"],
        "panel_id": data["panel_id"],
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "button_label": data.get("button_label", "Abrir Ticket"),
        "button_color": data.get("button_color", "blue"),
        "channel_id": str(channel_id),
        "category_id": str(data.get("category_id", "")) if data.get("category_id") else None,
    }
    
    event = PanelCreatedEvent(**event_data)
    bot.dispatch("ticket_panel_created", guild, event)
    return {"status": "ok"}

@router.post("/panel/updated")
async def panel_updated(request: Request):
    data = await request.json()
    logger.info(f"📥 panel/updated: {data}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    event = PanelUpdatedEvent(**data)
    bot.dispatch("ticket_panel_updated", guild, event)
    return {"status": "ok"}

@router.post("/panel/deleted")
async def panel_deleted(request: Request):
    data = await request.json()
    logger.info(f"📥 panel/deleted: {data}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    event = PanelDeletedEvent(**data)
    bot.dispatch("ticket_panel_deleted", guild, event.panel_id)
    return {"status": "ok"}

@router.post("/ticket/created")
async def ticket_created(request: Request):
    data = await request.json()
    logger.info(f"📥 ticket/created: {data}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    event = TicketCreatedEvent(**data)
    bot.dispatch("ticket_created", guild, event)
    return {"status": "ok"}

@router.post("/ticket/closed")
async def ticket_closed(request: Request):
    data = await request.json()
    logger.info(f"📥 ticket/closed: {data}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    event = TicketClosedEvent(**data)
    bot.dispatch("ticket_closed", guild, event)
    return {"status": "ok"}

@router.post("/ticket/claimed")
async def ticket_claimed(request: Request):
    data = await request.json()
    logger.info(f"📥 ticket/claimed: {data}")
    
    bot = request.app.state.bot
    guild = bot.get_guild(int(data["guild_id"]))
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    event = TicketClaimedEvent(**data)
    bot.dispatch("ticket_claimed", guild, event)
    return {"status": "ok"}