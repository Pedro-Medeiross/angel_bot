from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import secrets
import uvicorn
import asyncio
import logging
from src.core.config import config

logger = logging.getLogger(__name__)

# ═══════════════ AUTH MIDDLEWARE ═══════════════

async def verify_bot_auth(request: Request, call_next):
    """Middleware de autenticação Basic Auth"""
    public_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
    
    if request.url.path in public_paths or request.url.path.startswith("/docs"):
        return await call_next(request)
    
    auth = request.headers.get("Authorization", "")
    
    if not auth.startswith("Bearer "):
        logger.warning(f"Auth inválido: {auth[:20]}...")
        raise HTTPException(status_code=401, detail="Missing or invalid auth header")
    
    token = auth.replace("Bearer ", "")
    expected = f"{config.API_USER}:{config.API_PASS}"
    
    if not secrets.compare_digest(token, expected):
        logger.warning("Credenciais inválidas")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return await call_next(request)

# ═══════════════ APP FACTORY ═══════════════

def create_app(bot):
    """Cria o app FastAPI para receber eventos da API"""
    
    app = FastAPI(
        title="Bot Events Receiver",
        version="1.0.0",
        docs_url=None if not config.DEBUG else "/docs",
        redoc_url=None
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.state.bot = bot
    app.middleware("http")(verify_bot_auth)
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "bot-events"}
    
    from .routes import events
    app.include_router(events.router, prefix="/events", tags=["Events"])
    
    return app

# ═══════════════ SERVER LAUNCHER ═══════════════

def start_api_server(bot):
    """Inicia o servidor FastAPI"""
    app = create_app(bot)
    bot_port = int(getattr(config, 'BOT_PORT', '8001'))
    
    config_obj = uvicorn.Config(app, host="0.0.0.0", port=bot_port, log_level="info")
    server = uvicorn.Server(config_obj)
    
    # Compatível com Python 3.12+
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.create_task(server.serve())
    logger.info(f"🌐 Bot API listener em http://0.0.0.0:{bot_port}")