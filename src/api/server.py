from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import logging
from src.core.config import config

logger = logging.getLogger(__name__)

def create_app(bot):
    """Cria o app FastAPI para receber eventos da API"""
    
    app = FastAPI(title="Bot Events Receiver", version="1.0.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.state.bot = bot
    
    # Health check público
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "bot-events"}
    
    # Registra rotas
    from .routes import events
    app.include_router(events.router, prefix="/events", tags=["Events"])
    
    return app

def start_api_server(bot):
    """Inicia o servidor FastAPI"""
    app = create_app(bot)
    
    bot_port = int(getattr(config, 'BOT_PORT', '8001'))
    
    loop = asyncio.get_event_loop()
    config_obj = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=bot_port,
        log_level="info"
    )
    server = uvicorn.Server(config_obj)
    loop.create_task(server.serve())
    logger.info(f"🌐 Bot API listener em http://0.0.0.0:{bot_port}")