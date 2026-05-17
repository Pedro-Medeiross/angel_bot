import aiohttp
from typing import Optional
from src.core.config import config

class LogAPI:
    """Cliente HTTP para enviar logs para a API"""
    
    def __init__(self):
        self.base_url = config.API_URL
        self.auth = aiohttp.BasicAuth(config.API_USER, config.API_PASS)
    
    async def send_log(
        self,
        guild_id: int,
        log_type: str,
        user_id: Optional[int] = None,
        target_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        data: Optional[dict] = None
    ) -> Optional[dict]:
        """Envia um log para a API"""
        payload = {
            "log_type": log_type,
            "user_id": user_id,
            "target_id": target_id,
            "channel_id": channel_id,
            "data": data or {}
        }
        
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(f"{self.base_url}/guilds/{guild_id}/logs", json=payload) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"❌ Erro ao enviar log: {resp.status}")
        except aiohttp.ClientError as e:
            print(f"❌ Erro API log {log_type}: {e}")
        return None
    
    async def send_mod_log(
        self,
        guild_id: int,
        log_type: str,
        moderator,
        target,
        reason: Optional[str] = None,
        duration: Optional[str] = None,
        **kwargs
    ) -> Optional[dict]:
        """Envia log de comando moderativo"""
        return await self.send_log(
            guild_id=guild_id,
            log_type="moderator_commands",
            user_id=moderator.id,
            target_id=target.id,
            data={
                "command": log_type,
                "moderator_name": moderator.name,
                "moderator_display_name": moderator.display_name,
                "target_name": target.name,
                "target_display_name": getattr(target, 'display_name', target.name),
                "reason": reason or "Nenhuma razão informada",
                "duration": duration,
                **kwargs
            }
        )

log_api = LogAPI()