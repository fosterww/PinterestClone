from asyncio import to_thread
from typing import Any

from google.auth.transport import requests
from google.oauth2 import id_token

from core.config import settings


async def verify_google_token(token: str) -> dict[str, Any] | None:
    def verify():
        try:
            req = requests.Request()
            idinfo = id_token.verify_oauth2_token(
                token, req, settings.google_client_id, clock_skew_in_seconds=120
            )
            return dict(idinfo)
        except Exception as e:
            print(f"Google token verification failed: {e}")
            return None

    return await to_thread(verify)
