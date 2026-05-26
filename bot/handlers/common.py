"""Welcome / start dashboard and shared utilities."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

from context import BotContext

logger = logging.getLogger(__name__)


# ---- helpers (no DI needed – pure functions) ---------------------------

def extract_user_context(update: Update) -> dict:
    """Helper to cleanly extract Telegram user metadata."""
    user = update.effective_user
    return {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


async def clear_chat_footprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Evicts incoming text triggers and deletes the stale menu canvas."""
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    last_menu_id = context.user_data.get("active_menu_id")
    if last_menu_id:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=last_menu_id
            )
        except Exception as exc:
            logger.debug("Stale menu message already cleared: %s", exc)

        context.user_data["active_menu_id"] = None


# ---- handlers -----------------------------------------------------------

_WELCOME_TEXT = "Welcome to the Retail Bot! Use the options below to navigate:"


def _build_welcome_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")],
        [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user, syncs profile data, and initiates a clean dashboard."""
    await clear_chat_footprint(update, context)

    ctx: BotContext = context.application.bot_data["ctx"]
    user_ctx = extract_user_context(update)
    await ctx.api.sync_user(user_ctx)

    sent_msg = await update.effective_chat.send_message(
        text=_WELCOME_TEXT, reply_markup=_build_welcome_keyboard()
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the chat interface back to the main welcome menu canvas."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text=_WELCOME_TEXT, reply_markup=_build_welcome_keyboard()
    )


# ---- registration -------------------------------------------------------


def register_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        CommandHandler("catalog", start)
    )  # legacy alias – main menu
    app.add_handler(
        CommandHandler("cancel", start)
    )  # fallback command