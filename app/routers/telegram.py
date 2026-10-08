from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.services.discord_oauth import create_oauth_url


router = Router()


def main_keyboard(telegram_user_id: int) -> InlineKeyboardMarkup:
    login_url = create_oauth_url(telegram_user_id)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Login with Discord",
                    url=login_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Statistics",
                    callback_data="stats",
                ),
                InlineKeyboardButton(
                    text="👤 Accounts",
                    callback_data="accounts",
                ),
            ],
        ]
    )


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    text = (
        "⚡ <b>Z-Volt Discord Quest Completer</b>\n\n"
        "Welcome! 👋\n\n"
        "Connect your Discord account using the official "
        "Discord authorization system.\n\n"
        "🔐 Your Discord password or user token is never requested.\n\n"
        "Choose an option below:"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(user.id),
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
    )

    await message.answer(text)


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    await message.answer(
        "📊 <b>Statistics</b>\n\n"
        "Quest statistics will be available after "
        "your Discord account is connected."
    )


@router.message(Command("accounts"))
async def accounts_command(message: Message) -> None:
    await message.answer(
        "👤 <b>Connected Accounts</b>\n\n"
        "No persistent account list is configured yet."
    )


@router.message(Command("add"))
async def add_command(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    await message.answer(
        "➕ <b>Add Discord Account</b>\n\n"
        "Use the official Discord login button below.",
        reply_markup=main_keyboard(user.id),
    )