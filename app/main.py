import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request

from app.config import (
    APP_ENV,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    TELEGRAM_WEBHOOK_URL,
)

from app.routers.telegram import router as telegram_router


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Z-Volt Discord Quest Completer",
    version="0.1.0",
)


# ============================================================
# TELEGRAM BOT
# ============================================================

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()

dp.include_router(telegram_router)


telegram_polling_task = None


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Z-Volt Discord Quest Completer",
        "status": "online",
        "version": "0.1.0",
        "environment": APP_ENV,
        "auth": "token",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post(
    "/telegram/webhook/{secret}"
)
async def telegram_webhook(
    secret: str,
    request: Request,
):
    # --------------------------------------------------------
    # Validate webhook secret
    # --------------------------------------------------------

    if secret != TELEGRAM_WEBHOOK_SECRET:
        return {
            "ok": False,
            "error": "Unauthorized",
        }


    # --------------------------------------------------------
    # Read Telegram request
    # --------------------------------------------------------

    try:
        update_data = await request.json()

    except Exception as exc:

        print(
            "Telegram webhook JSON error: "
            f"{type(exc).__name__}: {exc}"
        )

        return {
            "ok": False,
            "error": "Invalid JSON",
        }


    # --------------------------------------------------------
    # Convert JSON into aiogram Update
    # --------------------------------------------------------

    try:

        from aiogram.types import Update

        update = Update.model_validate(
            update_data,
            context={
                "bot": bot,
            },
        )

    except Exception as exc:

        print(
            "Telegram update validation error: "
            f"{type(exc).__name__}: {exc}"
        )

        return {
            "ok": False,
            "error": "Invalid Telegram update",
        }


    # --------------------------------------------------------
    # Process Telegram update
    # --------------------------------------------------------

    try:

        await dp.feed_update(
            bot,
            update,
        )

    except Exception as exc:

        print(
            "Telegram update processing error: "
            f"{type(exc).__name__}: {exc}"
        )

        # Return 200 so Telegram doesn't repeatedly resend
        # the same problematic update forever.
        return {
            "ok": True,
        }


    return {
        "ok": True,
    }


# ============================================================
# LOCAL TELEGRAM POLLING
# ============================================================

async def telegram_polling() -> None:

    print(
        "Starting Telegram polling..."
    )

    try:

        await bot.delete_webhook(
            drop_pending_updates=True,
        )

        await dp.start_polling(
            bot,
        )

    except asyncio.CancelledError:

        print(
            "Telegram polling cancelled."
        )

        raise

    except Exception as exc:

        print(
            "Telegram polling error: "
            f"{type(exc).__name__}: {exc}"
        )

        raise


# ============================================================
# PRODUCTION TELEGRAM WEBHOOK SETUP
# ============================================================

async def setup_webhook() -> None:

    if not TELEGRAM_WEBHOOK_URL:

        print(
            "TELEGRAM_WEBHOOK_URL is not configured."
        )

        return


    webhook_url = (
        f"{TELEGRAM_WEBHOOK_URL}"
        f"/telegram/webhook/"
        f"{TELEGRAM_WEBHOOK_SECRET}"
    )


    try:

        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
        )

        print(
            "Telegram webhook configured: "
            f"{webhook_url}"
        )

    except Exception as exc:

        print(
            "Telegram webhook setup error: "
            f"{type(exc).__name__}: {exc}"
        )

        raise


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    global telegram_polling_task


    print(
        "Starting Z-Volt Discord Quest Completer..."
    )

    print(
        f"Environment: {APP_ENV}"
    )


    # --------------------------------------------------------
    # Production = Telegram webhook
    # --------------------------------------------------------

    if APP_ENV == "production":

        await setup_webhook()

        print(
            "Production mode: Telegram webhook enabled."
        )

        return


    # --------------------------------------------------------
    # Development = Telegram polling
    # --------------------------------------------------------

    telegram_polling_task = asyncio.create_task(
        telegram_polling()
    )

    print(
        "Development mode: Telegram polling enabled."
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    global telegram_polling_task


    # --------------------------------------------------------
    # Stop local polling
    # --------------------------------------------------------

    if telegram_polling_task:

        telegram_polling_task.cancel()

        try:

            await telegram_polling_task

        except asyncio.CancelledError:

            pass

        except Exception as exc:

            print(
                "Polling shutdown error: "
                f"{type(exc).__name__}: {exc}"
            )


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT delete the Telegram production webhook here.
    #
    # Render can restart/sleep/wake the service.
    # Deleting the webhook during shutdown would cause
    # Telegram updates to stop arriving after restart.
    # --------------------------------------------------------

    try:

        await bot.session.close()

    except Exception as exc:

        print(
            "Telegram bot session close error: "
            f"{type(exc).__name__}: {exc}"
        )


# ============================================================
# DIRECT PYTHON START
# ============================================================

if __name__ == "__main__":

    import uvicorn


    port = int(
        os.getenv(
            "PORT",
            "8000",
        )
    )


    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
    )
