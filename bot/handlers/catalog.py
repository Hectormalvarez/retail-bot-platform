import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import fetch_products, sync_user
from handlers.common import extract_user_context

logger = logging.getLogger(__name__)


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queries the API container and renders interactive menus."""
    user_ctx = extract_user_context(update)
    await sync_user(user_ctx)  # Dispatched safe check

    products = await fetch_products()

    if not products:
        text = "The catalog is currently empty or down for maintenance."
        await update.message.reply_text(text)
        return

    keyboard = []
    for item in products:
        button_text = f"{item['name']} — ${item['price']}"
        callback_data = f"view_prod_{item['id']}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = "📦 *Available Products*:\nSelect an item to view details:"
    await update.message.reply_text(
        text=menu_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def view_product_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Fetches and displays the deep-dive card for a specific product."""
    query = update.callback_query
    await query.answer()

    logger.info(f"Catalog callback invoked: {query.data}")

    product_id = query.data.split("_")[-1]
    await query.message.reply_text(
        f"Modular routing success! Parsed product ID target: {product_id}"
    )


async def send_sync_payload(user_ctx: dict):
    """Inline proxy placeholder for decoupled sync requests."""
    from api_client import sync_user

    await sync_user(user_ctx)
