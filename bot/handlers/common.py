import logging

from telegram import Update
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and ensures their profile is synced to PG."""
    user_ctx = extract_user_context(update)
    await sync_user(user_ctx)

    text = "Welcome to the Retail Bot! Use /catalog to view active items."
    await update.message.reply_text(text)
