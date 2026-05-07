from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import secrets
import uvicorn
import asyncio
import logging
from src.core.config import config

logger = logging.getLogger(__name__)

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
    
    # Middleware de autenticação
    @app.middleware("http")
    async def verify_bot_auth(request: Request, call_next):
        # Health check público
        if request.url.path == "/health":
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization", "")
        logger.debug(f"Auth header: {auth_header[:50]}...")
        
        # Aceita "Bearer user:pass" ou "Basic base64"
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            expected = f"{config.API_USER}:{config.API_PASS}"
            
            if not secrets.compare_digest(token, expected):
                logger.warning(f"Bearer token inválido")
                raise HTTPException(status_code=401, detail="Invalid credentials")
        
        elif auth_header.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth_header.replace("Basic ", "")).decode()
                user, passwd = decoded.split(":", 1)
                if user != config.API_USER or passwd != config.API_PASS:
                    raise HTTPException(status_code=401, detail="Invalid credentials")
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid Basic auth")
        
        else:
            logger.warning(f"Header inválido: {auth_header[:20]}")
            raise HTTPException(status_code=401, detail="Missing auth")
        
        return await call_next(request)
    
    # Health check
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