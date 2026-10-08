import asyncio
import html
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
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
    DiscordOAuthRateLimited,
    consume_state,
    exchange_code,
    get_discord_user,
    get_state_user,
)


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
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


# ============================================================
# DISCORD OAUTH CALLBACK
# ============================================================

@app.get(
    "/auth/discord/callback",
    response_class=HTMLResponse,
)
async def discord_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    # --------------------------------------------------------
    # Discord cancelled / rejected authorization
    # --------------------------------------------------------

    if error:
        safe_error = html.escape(
            error_description or error
        )

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width,
                    initial-scale=1.0"
                >

                <title>Discord Login Cancelled</title>

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
                        color: #f87171;
                    }}

                    p {{
                        line-height: 1.6;
                    }}
                </style>
            </head>

            <body>

                <div class="card">

                    <h1>❌ Discord Authorization Cancelled</h1>

                    <p>
                        Discord did not authorize the connection.
                    </p>

                    <p>
                        Reason:
                        <strong>{safe_error}</strong>
                    </p>

                    <p>
                        You can close this page and return to Telegram.
                    </p>

                </div>

            </body>
            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # Missing OAuth parameters
    # --------------------------------------------------------

    if not code or not state:
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width,
                    initial-scale=1.0"
                >

                <title>Invalid Discord Login</title>

                <style>
                    body {
                        margin: 0;
                        padding: 40px 20px;
                        background: #0b0f0d;
                        color: #ffffff;
                        font-family: Arial, sans-serif;
                        text-align: center;
                    }

                    .card {
                        max-width: 520px;
                        margin: 40px auto;
                        padding: 35px;
                        border-radius: 20px;
                        background: #111816;
                        border: 1px solid #26352f;
                    }

                    h1 {
                        color: #f87171;
                    }

                    p {
                        line-height: 1.6;
                    }
                </style>
            </head>

            <body>

                <div class="card">

                    <h1>❌ Invalid OAuth Callback</h1>

                    <p>
                        Discord did not provide the required
                        authorization information.
                    </p>

                    <p>
                        Please return to Telegram and start
                        a new Discord login.
                    </p>

                </div>

            </body>
            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # Find Telegram user associated with OAuth state
    # --------------------------------------------------------

    telegram_user_id = get_state_user(state)

    if telegram_user_id is None:
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width,
                    initial-scale=1.0"
                >

                <title>Expired Discord Login</title>

                <style>
                    body {
                        margin: 0;
                        padding: 40px 20px;
                        background: #0b0f0d;
                        color: #ffffff;
                        font-family: Arial, sans-serif;
                        text-align: center;
                    }

                    .card {
                        max-width: 520px;
                        margin: 40px auto;
                        padding: 35px;
                        border-radius: 20px;
                        background: #111816;
                        border: 1px solid #26352f;
                    }

                    h1 {
                        color: #facc15;
                    }

                    p {
                        line-height: 1.6;
                    }
                </style>
            </head>

            <body>

                <div class="card">

                    <h1>⏳ Login Session Expired</h1>

                    <p>
                        This Discord login session is no longer valid.
                    </p>

                    <p>
                        Please return to Telegram and press
                        <strong>Login with Discord</strong> again.
                    </p>

                </div>

            </body>
            </html>
            """,
            status_code=400,
        )


    # --------------------------------------------------------
    # Exchange Discord authorization code
    # --------------------------------------------------------

    try:

        token_data = await exchange_code(code)

        access_token = token_data.get("access_token")

        if not access_token:
            print(
                "Discord OAuth error: "
                "No access_token returned."
            )

            return HTMLResponse(
                """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">

                    <meta
                        name="viewport"
                        content="width=device-width,
                        initial-scale=1.0"
                    >

                    <title>Discord Login Error</title>
                </head>

                <body>

                    <h2>❌ Discord Login Failed</h2>

                    <p>
                        Discord did not return an access token.
                    </p>

                    <p>
                        Please return to Telegram and try again.
                    </p>

                </body>
                </html>
                """,
                status_code=500,
            )


        # ----------------------------------------------------
        # Get Discord account information
        # ----------------------------------------------------

        discord_user = await get_discord_user(
            access_token
        )


        # ----------------------------------------------------
        # OAuth succeeded.
        #
        # Only now consume the state.
        # ----------------------------------------------------

        consume_state(state)


    # --------------------------------------------------------
    # Discord OAuth rate limit
    # --------------------------------------------------------

    except DiscordOAuthRateLimited as exc:

        retry_seconds = 60

        if exc.retry_after is not None:
            try:
                retry_seconds = max(
                    1,
                    round(float(exc.retry_after)),
                )
            except (
                TypeError,
                ValueError,
            ):
                retry_seconds = 60


        print(
            "Discord OAuth rate limited. "
            f"retry_after={retry_seconds}"
        )


        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>

            <head>
                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width,
                    initial-scale=1.0"
                >

                <title>Discord Rate Limited</title>

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
                        color: #facc15;
                    }}

                    .time {{
                        font-size: 28px;
                        font-weight: bold;
                        margin: 25px 0;
                        color: #4ade80;
                    }}

                    p {{
                        line-height: 1.6;
                    }}
                </style>
            </head>

            <body>

                <div class="card">

                    <h1>⏳ Discord Rate Limit</h1>

                    <p>
                        Discord is temporarily limiting
                        OAuth requests for this application.
                    </p>

                    <div class="time">
                        {retry_seconds} seconds
                    </div>

                    <p>
                        Please wait before starting another
                        Discord login.
                    </p>

                    <p>
                        Then return to Telegram and use
                        <strong>Login with Discord</strong>
                        again.
                    </p>

                </div>

            </body>

            </html>
            """,
            status_code=429,
            headers={
                "Retry-After": str(retry_seconds),
            },
        )


    # --------------------------------------------------------
    # HTTP errors / unexpected Discord errors
    # --------------------------------------------------------

    except Exception as exc:

        print(
            "Discord OAuth error: "
            f"{type(exc).__name__}: {exc}"
        )

        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>

            <head>
                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width,
                    initial-scale=1.0"
                >

                <title>Discord Login Failed</title>

                <style>
                    body {
                        margin: 0;
                        padding: 40px 20px;
                        background: #0b0f0d;
                        color: #ffffff;
                        font-family: Arial, sans-serif;
                        text-align: center;
                    }

                    .card {
                        max-width: 520px;
                        margin: 40px auto;
                        padding: 35px;
                        border-radius: 20px;
                        background: #111816;
                        border: 1px solid #26352f;
                    }

                    h1 {
                        color: #f87171;
                    }

                    p {
                        line-height: 1.6;
                    }
                </style>
            </head>

            <body>

                <div class="card">

                    <h1>❌ Discord Login Failed</h1>

                    <p>
                        Something went wrong while connecting
                        your Discord account.
                    </p>

                    <p>
                        Please return to Telegram and start
                        a new Discord login.
                    </p>

                </div>

            </body>
            </html>
            """,
            status_code=500,
        )


    # --------------------------------------------------------
    # Extract Discord account information safely
    # --------------------------------------------------------

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

    safe_global_name = html.escape(
        str(global_name)
    )

    safe_username = html.escape(
        str(username)
    )

    safe_discord_id = html.escape(
        str(discord_id)
    )


    print(
        "Discord account connected: "
        f"telegram_user={telegram_user_id}, "
        f"discord_id={discord_id}, "
        f"username={username}"
    )


    # --------------------------------------------------------
    # SUCCESS PAGE
    # --------------------------------------------------------

    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>

        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width,
                initial-scale=1.0"
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
                    box-shadow:
                        0 20px 60px
                        rgba(0, 0, 0, 0.35);
                }}

                h1 {{
                    color: #4ade80;
                    margin-bottom: 25px;
                }}

                .account {{
                    margin: 25px 0;
                    padding: 20px;
                    border-radius: 14px;
                    background: #18221e;
                    border: 1px solid #26352f;
                }}

                .item {{
                    margin: 18px 0;
                }}

                .label {{
                    color: #9ca3af;
                    font-size: 14px;
                    margin-bottom: 5px;
                }}

                .value {{
                    font-size: 18px;
                    font-weight: bold;
                    word-break: break-word;
                }}

                p {{
                    line-height: 1.6;
                }}

                .success {{
                    color: #86efac;
                    font-weight: bold;
                }}
            </style>
        </head>

        <body>

            <div class="card">

                <h1>✅ Discord Connected</h1>

                <p class="success">
                    Your Discord account was successfully connected.
                </p>

                <div class="account">

                    <div class="item">
                        <div class="label">
                            Account
                        </div>

                        <div class="value">
                            {safe_global_name}
                        </div>
                    </div>


                    <div class="item">
                        <div class="label">
                            Username
                        </div>

                        <div class="value">
                            {safe_username}
                        </div>
                    </div>


                    <div class="item">
                        <div class="label">
                            Discord ID
                        </div>

                        <div class="value">
                            {safe_discord_id}
                        </div>
                    </div>

                </div>

                <p>
                    You can close this page and return to Telegram.
                </p>

            </div>

        </body>

        </html>
        """,
        status_code=200,
    )


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
