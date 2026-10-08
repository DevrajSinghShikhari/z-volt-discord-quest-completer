import secrets
from urllib.parse import urlencode

import httpx

from app.config import (
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
)


DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_BASE = "https://discord.com/api/v10"


# Temporary local storage.
# We will replace this with PostgreSQL later.
_pending_states: dict[str, int] = {}


def create_oauth_url(telegram_user_id: int) -> str:
    state = secrets.token_urlsafe(32)

    _pending_states[state] = telegram_user_id

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }

    return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


def consume_state(state: str) -> int | None:
    return _pending_states.pop(state, None)


async def exchange_code(code: str) -> dict:
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            DISCORD_TOKEN_URL,
            data=data,
            headers=headers,
        )

    response.raise_for_status()

    return response.json()


async def get_discord_user(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers=headers,
        )

    response.raise_for_status()

    return response.json()