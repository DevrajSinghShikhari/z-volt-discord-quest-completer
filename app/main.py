import asyncio
import html
import os

from aiogram import Bot, Dispatcher
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.config import (
    APP_ENV,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    TELEGRAM_WEBHOOK_URL,
)
from app.routers.telegram import router as telegram_router
from app.services.discord_oauth import (
    consume_state,
    exchange_code,
    get_discord_user,
)


app = FastAPI(
    title="Z-Volt Discord Quest Completer",
    version="0.1.0",
)


bot = Bot(token=TELEGRAM_BOT_TOKEN)

dp = Dispatcher()

dp.include_router(telegram_router)

telegram_polling_task = None


@app.get("/")
async def root():
    return {
        "name": "Z-Volt Discord Quest Completer",
        "status": "online",
        "version": "0.1.0",
        "environment": APP_ENV,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


@app.get("/auth/discord/callback", response_class=HTMLResponse)
async def discord_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Discord Login</title>
            </head>
            <body>
                <h2>❌ Discord authorization cancelled</h2>
                <p>{html.escape(error)}</p>
                <p>You can close this window and return to Telegram.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    if not code or not state:
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Discord Login</title>
            </head>
            <body>
                <h2>❌ Invalid OAuth callback</h2>
                <p>Missing authorization code or state.</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    telegram_user_id = consume_state(state)

    if telegram_user_id is None:
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Discord Login</title>
            </head>
            <body>
                <h2>❌ Invalid or expired login session</h2>
                <p>
                    Please return to Telegram and press
                    Login with Discord again.
                </p>
            </body>
            </html>
            """,
            status_code=400,
        )

    try:
        token_data = await exchange_code(code)

        access_token = token_data["access_token"]

        discord_user = await get_discord_user(access_token)

    except Exception as exc:
        print(f"Discord OAuth error: {exc}")

        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Discord Login</title>
            </head>
            <body>
                <h2>❌ Discord login failed</h2>
                <p>Please return to Telegram and try again.</p>
            </body>
            </html>
            """,
            status_code=500,
        )

    username = discord_user.get(
        "username",
        "Unknown",
    )

    global_name = (
        discord_user.get("global_name")
        or username
    )

    discord_id = discord_user.get(
        "id",
        "Unknown",
    )

    print(
        "Discord account connected: "
        f"telegram_user={telegram_user_id}, "
        f"discord_id={discord_id}, "
        f"username={username}"
    )

    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >
            <title>Z-Volt Discord Quest Completer</title>

            <style>
                body {{
                    margin: 0;
                    padding: 40px 20px;
                    background: #0b0f0d;
                    color: #ffffff;
                    font-family: Arial, sans-serif;
                    text-align: center;
                }}

                .card {{
                    max-width: 520px;
                    margin: 40px auto;
                    padding: 35px;
                    border-radius: 20px;
                    background: #111816;
                    border: 1px solid #26352f;
                }}

                h1 {{
                    color: #4ade80;
                }}

                .account {{
                    margin: 25px 0;
                    padding: 20px;
                    border-radius: 14px;
                    background: #18221e;
                }}

                p {{
                    line-height: 1.6;
                }}
            </style>
        </head>

        <body>

            <div class="card">

                <h1>✅ Discord Connected</h1>

                <div class="account">

                    <p>
                        <strong>Account</strong><br>
                        {html.escape(global_name)}
                    </p>

                    <p>
                        <strong>Username</strong><br>
                        {html.escape(username)}
                    </p>

                    <p>
                        <strong>Discord ID</strong><br>
                        {html.escape(discord_id)}
                    </p>

                </div>

                <p>
                    Your Discord account was successfully connected.
                </p>

                <p>
                    You can close this page and return to Telegram.
                </p>

            </div>

        </body>
        </html>
        """
    )


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
):
    if secret != TELEGRAM_WEBHOOK_SECRET:
        return {
            "ok": False,
            "error": "Unauthorized",
        }

    update_data = await request.json()

    from aiogram.types import Update

    update = Update.model_validate(
        update_data,
        context={"bot": bot},
    )

    await dp.feed_update(
        bot,
        update,
    )

    return {
        "ok": True,
    }


async def telegram_polling() -> None:
    print("Starting Telegram polling...")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(bot)


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

    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
    )

    print(
        "Telegram webhook configured:"
        f" {TELEGRAM_WEBHOOK_URL}"
    )


@app.on_event("startup")
async def startup_event():
    global telegram_polling_task

    if APP_ENV == "production":
        await setup_webhook()

    else:
        telegram_polling_task = asyncio.create_task(
            telegram_polling()
        )


@app.on_event("shutdown")
async def shutdown_event():
    global telegram_polling_task

    if telegram_polling_task:
        telegram_polling_task.cancel()

        try:
            await telegram_polling_task
        except asyncio.CancelledError:
            pass

    if APP_ENV == "production":
        try:
            await bot.delete_webhook()
        except Exception:
            pass

    await bot.session.close()


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