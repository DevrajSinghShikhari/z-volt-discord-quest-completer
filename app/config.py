import os

from dotenv import load_dotenv


load_dotenv()


def get_required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


TELEGRAM_BOT_TOKEN = get_required("TELEGRAM_BOT_TOKEN")

DISCORD_CLIENT_ID = get_required("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = get_required("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = get_required("DISCORD_REDIRECT_URI")

DATABASE_URL = os.getenv("DATABASE_URL", "")

APP_ENV = os.getenv("APP_ENV", "development")

# Used only in production.
# Example:
# https://zvoltquestcompleter.xcloud.ar
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").rstrip("/")

# Secret path used by Telegram webhook.
TELEGRAM_WEBHOOK_SECRET = os.getenv(
    "TELEGRAM_WEBHOOK_SECRET",
    "zvolt-telegram-webhook-secret",
)