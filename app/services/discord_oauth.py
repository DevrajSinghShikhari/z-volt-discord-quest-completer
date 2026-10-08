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


# Temporary OAuth state storage.
# This will later be moved to PostgreSQL.
_pending_states: dict[str, int] = {}


class DiscordOAuthRateLimited(Exception):
    """Raised when Discord rate-limits the OAuth token request."""

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after

        if retry_after is not None:
            message = (
                f"Discord OAuth is rate-limited. "
                f"Retry after {retry_after} seconds."
            )
        else:
            message = "Discord OAuth is temporarily rate-limited."

        super().__init__(message)


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


def get_state_user(state: str) -> int | None:
    """
    Read the Telegram user ID without consuming the OAuth state.
    This allows us to keep the state if Discord temporarily
    rate-limits the token exchange.
    """
    return _pending_states.get(state)


def consume_state(state: str) -> int | None:
    """
    Consume an OAuth state after the Discord token exchange
    has succeeded.
    """
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

    # Discord OAuth rate limit
    if response.status_code == 429:
        retry_after = None

        try:
            body = response.json()

            value = body.get("retry_after")

            if value is not None:
                retry_after = float(value)

        except Exception:
            pass

        if retry_after is None:
            header_value = response.headers.get("Retry-After")

            if header_value:
                try:
                    retry_after = float(header_value)
                except ValueError:
                    pass

        print(
            "Discord OAuth rate limited. "
            f"retry_after={retry_after}"
        )

        raise DiscordOAuthRateLimited(retry_after)

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
