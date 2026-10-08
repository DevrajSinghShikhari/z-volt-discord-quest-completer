"""
Token-based Discord authentication.

Replaces the OAuth2 authorization-code flow.

Why:
- POST /oauth2/token is aggressively IP rate-limited (429 on Render's shared IPs)
- The code flow needs a working redirect_uri + public callback route
- A user token needs neither: one GET /users/@me validates it, then connect

Get a token: discord.com -> F12 -> Console -> localStorage.getItem("token")
"""

from __future__ import annotations

import httpx

DISCORD_API_BASE = "https://discord.com/api/v10"

# telegram_user_id -> {"token": str, "discord_id": int, "username": str, "global_name": str|None}
_sessions: dict[int, dict] = {}

# telegram_user_ids we are currently expecting to paste a token
_awaiting_token: set[int] = set()


class DiscordTokenInvalid(Exception):
    """Raised when Discord rejects the pasted token (401)."""


class DiscordAuthRateLimited(Exception):
    """Raised when Discord rate-limits the token validation call (429)."""

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__("Discord is temporarily rate-limiting us. Try again in a moment.")


# --------------------------------------------------------------------------
# Login state (who is expected to send a token)
# --------------------------------------------------------------------------

def start_login(telegram_user_id: int) -> None:
    _awaiting_token.add(telegram_user_id)


def is_awaiting_token(telegram_user_id: int) -> bool:
    return telegram_user_id in _awaiting_token


def cancel_login(telegram_user_id: int) -> None:
    _awaiting_token.discard(telegram_user_id)


# --------------------------------------------------------------------------
# Session storage (move to Postgres later, same as you planned)
# --------------------------------------------------------------------------

def save_session(telegram_user_id: int, token: str, discord_user: dict) -> None:
    _sessions[telegram_user_id] = {
        "token": token,
        "discord_id": int(discord_user["id"]),
        "username": discord_user.get("username"),
        "global_name": discord_user.get("global_name"),
    }


def get_session(telegram_user_id: int) -> dict | None:
    return _sessions.get(telegram_user_id)


def get_token(telegram_user_id: int) -> str | None:
    session = _sessions.get(telegram_user_id)
    return session["token"] if session else None


def remove_session(telegram_user_id: int) -> None:
    _sessions.pop(telegram_user_id, None)
    _awaiting_token.discard(telegram_user_id)


# --------------------------------------------------------------------------
# Token handling
# --------------------------------------------------------------------------

def clean_token(raw: str) -> str:
    """Tolerate quotes, backticks, whitespace and stray prefixes."""
    token = raw.strip().strip('"').strip("'").strip("`").strip()

    for prefix in ("Bearer ", "Bot ", "token=", "Token="):
        if token.startswith(prefix):
            token = token[len(prefix):].strip()

    return token


def looks_like_token(value: str) -> bool:
    """Discord user tokens are three base64url-ish parts separated by dots."""
    parts = value.split(".")
    return len(parts) == 3 and all(len(p) >= 6 for p in parts)


async def fetch_discord_user(token: str) -> dict:
    """GET /users/@me with the raw token. No 'Bot ' prefix for user tokens."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": token},
        )

    if response.status_code == 401:
        raise DiscordTokenInvalid("Discord rejected this token.")

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

        print(f"Discord rate limited on /users/@me. retry_after={retry_after}")
        raise DiscordAuthRateLimited(retry_after)

    response.raise_for_status()
    return response.json()


async def login_with_token(telegram_user_id: int, raw_token: str) -> dict:
    """Validate the token, store the session, return the Discord user."""
    token = clean_token(raw_token)

    if not looks_like_token(token):
        raise DiscordTokenInvalid(
            "That doesn't look like a Discord token (expected three parts separated by dots)."
        )

    discord_user = await fetch_discord_user(token)

    save_session(telegram_user_id, token, discord_user)
    cancel_login(telegram_user_id)

    return discord_user
