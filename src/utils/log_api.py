import aiohttp
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
        user_id: int = None,
        target_id: int = None,
        channel_id: int = None,
        data: dict = None
    ) -> dict | None:
        """Envia um log para a API"""
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                url = f"{self.base_url}/guilds/{guild_id}/logs"
                async with session.post(url, json={
                    "log_type": log_type,
                    "user_id": user_id,
                    "target_id": target_id,
                    "channel_id": channel_id,
                    "data": data or {}
                }) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        print(f"❌ Erro ao enviar log: {resp.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"❌ Erro API log {log_type}: {e}")
            return None
    
    async def send_mod_log(
        self,
        guild_id: int,
        log_type: str,
        moderator: discord.Member,
        target: discord.Member | discord.User,
        reason: str = None,
        duration: str = None,
        **kwargs
    ) -> dict | None:
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