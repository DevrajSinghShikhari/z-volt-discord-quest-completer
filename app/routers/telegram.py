from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.services import discord_oauth


router = Router()

LOGIN_CALLBACK = "discord_login"
STATS_CALLBACK = "stats"
ACCOUNTS_CALLBACK = "accounts"


TOKEN_HELP = (
    "🔐 <b>Connect your Discord account</b>\n\n"
    "Send your Discord <b>token</b> as your next message.\n\n"
    "<b>How to get it</b>\n"
    "1. Open <code>discord.com</code> in a desktop browser and log in\n"
    "2. Press <b>F12</b> → <b>Console</b>\n"
    "3. Paste this and press Enter:\n"
    "<code>localStorage.getItem(\"token\")</code>\n"
    "4. Copy the value it prints (starts with <code>MTA…</code>) "
    "and send it here\n\n"
    "It is not your password, and not a bot token.\n"
    "Revoke it anytime with <i>Log Out of All Devices</i>."
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Login with Discord",
                    callback_data=LOGIN_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Statistics",
                    callback_data=STATS_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="👤 Accounts",
                    callback_data=ACCOUNTS_CALLBACK,
                ),
            ],
        ]
    )


def account_label(session: dict) -> str:
    return (
        session.get("global_name")
        or session.get("username")
        or "Unknown"
    )


# ============================================================
# COMMANDS
# ============================================================

@router.message(Command("start"))
async def start_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    session = discord_oauth.get_session(user.id)

    if session:
        status = (
            f"✅ Connected as <b>{account_label(session)}</b>\n\n"
            "Choose an option below:"
        )
    else:
        status = (
            "Connect your Discord account with the "
            "🔐 <b>Login with Discord</b> button below.\n\n"
            "⚡ Token login — no OAuth rate limits, no password."
        )

    text = (
        "⚡ <b>Z-Volt Discord Quest Completer</b>\n\n"
        "Welcome! 👋\n\n"
        f"{status}"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    text = (
        "⚡ <b>Z-Volt Discord Quest Completer</b>\n\n"
        "<b>Commands</b>\n\n"
        "/start — Open the main menu\n"
        "/help — Show this help\n"
        "/stats — View statistics\n"
        "/accounts — View connected accounts\n"
        "/add — Add a Discord account\n"
        "/login — Connect a Discord account\n"
        "/logout — Forget the connected account\n"
    )

    await message.answer(text)


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    await send_stats(message)


@router.message(Command("accounts"))
async def accounts_command(message: Message) -> None:
    await send_accounts(message)


@router.message(Command("add"))
async def add_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    await message.answer(
        "➕ <b>Add Discord Account</b>\n\n"
        "Press the button below to connect a Discord account.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("login"))
async def login_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    discord_oauth.start_login(user.id)

    await message.answer(TOKEN_HELP)


@router.message(Command("logout"))
async def logout_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    discord_oauth.remove_session(user.id)

    await message.answer(
        "👋 Logged out. Your Discord token has been forgotten."
    )


# ============================================================
# SHARED VIEWS
# ============================================================

async def send_stats(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    session = discord_oauth.get_session(user.id)

    if not session:
        await message.answer(
            "📊 <b>Statistics</b>\n\n"
            "No Discord account connected yet.\n"
            "Use 🔐 <b>Login with Discord</b> to connect one.",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        "📊 <b>Statistics</b>\n\n"
        f"Account: <b>{account_label(session)}</b>\n\n"
        "Quest statistics will be available after "
        "your first quest run."
    )


async def send_accounts(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    session = discord_oauth.get_session(user.id)

    if not session:
        await message.answer(
            "👤 <b>Connected Accounts</b>\n\n"
            "No account connected yet.\n"
            "Use 🔐 <b>Login with Discord</b> to connect one.",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        "👤 <b>Connected Accounts</b>\n\n"
        f"• <b>{account_label(session)}</b> "
        f"(<code>{session['discord_id']}</code>)"
    )


# ============================================================
# CALLBACKS
# ============================================================

@router.callback_query(F.data == LOGIN_CALLBACK)
async def on_login_button(callback: CallbackQuery) -> None:
    await callback.answer()

    user = callback.from_user

    if user is None:
        return

    discord_oauth.start_login(user.id)

    await callback.message.answer(TOKEN_HELP)


@router.callback_query(F.data == STATS_CALLBACK)
async def on_stats_button(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_stats(callback.message)


@router.callback_query(F.data == ACCOUNTS_CALLBACK)
async def on_accounts_button(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_accounts(callback.message)


# ============================================================
# TOKEN PASTE
#
# Keep this registered LAST so it does not swallow commands.
# ============================================================

@router.message(F.text, ~F.text.startswith("/"))
async def on_pasted_token(message: Message) -> None:
    user = message.from_user

    if user is None or not message.text:
        return

    if not discord_oauth.is_awaiting_token(user.id):
        return

    try:
        discord_user = await discord_oauth.login_with_token(
            user.id,
            message.text,
        )

    except discord_oauth.DiscordTokenInvalid as exc:
        await message.reply(
            f"❌ {exc}\n\nSend the token again, or /login to restart."
        )
        return

    except discord_oauth.DiscordAuthRateLimited as exc:
        await message.reply(
            f"⏳ {exc}\n\nSend the token again in a few seconds."
        )
        return

    except Exception as exc:
        await message.reply(
            f"❌ Login failed: <code>{exc}</code>"
        )
        return

    # Hide the message containing the token where allowed
    try:
        await message.delete()
    except Exception:
        pass

    name = (
        discord_user.get("global_name")
        or discord_user.get("username")
        or "Unknown"
    )

    await message.answer(
        f"✅ <b>Discord connected</b>\n\n"
        f"Logged in as <b>{name}</b> "
        f"(<code>{discord_user['id']}</code>).\n\n"
        "Your token is saved. Run a quest to get started.",
        reply_markup=main_keyboard(),
    )
