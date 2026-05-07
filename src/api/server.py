from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import uvicorn
import asyncio
import logging
from src.core.config import config

logger = logging.getLogger(__name__)
security = HTTPBasic()

def create_app(bot):
    """Cria o app FastAPI para receber eventos da API"""
    
    app = FastAPI(title="Bot Events Receiver", version="1.0.0")
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Guarda referência do bot
    app.state.bot = bot
    
    # Middleware de autenticação Basic Auth
    @app.middleware("http")
    async def verify_bot_auth(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing auth")
        
        token = auth_header.replace("Bearer ", "")
        expected = f"{config.API_USER}:{config.API_PASS}"
        
        if not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return await call_next(request)
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "bot-events"}
    
    # Registra rotas de eventos
    from .routes import events
    app.include_router(events.router, prefix="/events", tags=["Events"])
    
    return app

def start_api_server(bot):
    """Inicia o servidor FastAPI em uma task"""
    app = create_app(bot)
    
    bot_port = int(config.BOT_PORT) if hasattr(config, 'BOT_PORT') else 8001
    
    loop = asyncio.get_event_loop()
    config_obj = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=bot_port,
        log_level="info"
    )
    server = uvicorn.Server(config_obj)
    loop.create_task(server.serve())
    logger.info(f"🌐 Bot API listener iniciado em http://0.0.0.0:{bot_port}")