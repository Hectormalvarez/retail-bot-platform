import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import sync_user

logger = logging.getLogger(__name__)


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
            logger.debug(f"Stale menu message already cleared: {exc}")

        context.user_data["active_menu_id"] = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user, syncs profile data, and initiates a clean dashboard."""
    await clear_chat_footprint(update, context)

    user_ctx = extract_user_context(update)
    await sync_user(user_ctx)

    text = "Welcome to the Retail Bot! Use the options below to navigate:"
    keyboard = [
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")],
        [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")],
    ]

    sent_msg = await update.effective_chat.send_message(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the chat interface back to the main welcome menu canvas."""
    query = update.callback_query
    await query.answer()

    text = "Welcome to the Retail Bot! Use the options below to navigate:"
    keyboard = [
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")],
        [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")],
    ]

    await query.edit_message_text(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard)
    )
