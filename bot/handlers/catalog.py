import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import fetch_product_detail, fetch_products, sync_user
from handlers.common import extract_user_context

logger = logging.getLogger(__name__)


def _build_catalog_keyboard(products: list) -> InlineKeyboardMarkup:
    """Helper to format the vertical grid of catalog product buttons."""
    keyboard = []
    for item in products:
        button_text = f"{item['name']} — ${item['price']}"
        callback_data = f"view_prod_{item['id']}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )
    return InlineKeyboardMarkup(keyboard)


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queries the API container and renders interactive menus."""
    user_ctx = extract_user_context(update)
    await sync_user(user_ctx)

    products = await fetch_products()

    if not products:
        text = "The catalog is currently empty or down for maintenance."
        await update.message.reply_text(text)
        return

    reply_markup = _build_catalog_keyboard(products)
    menu_text = "📦 *Available Products*:\nSelect an item to view details:"
    await update.message.reply_text(
        text=menu_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def view_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the deep-dive card for a specific product."""
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[-1])
    product = await fetch_product_detail(product_id)

    if not product:
        await query.message.reply_text("Product record could not be found.")
        return

    # Render a clean Markdown detail card
    card_text = (
        f"📦 *{product['name']}*\n"
        f"Category: {product['category_name']}\n"
        f"Price: ${product['price']}\n"
        f"Stock: {product['stock']} available\n\n"
        f"_{product['description']}_"
    )

    # UI Controls: Add to Cart (Stubbed for Commit 15) and Back navigation
    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 Add to Cart", callback_data=f"add_to_cart_{product['id']}"
            )
        ],
        [InlineKeyboardButton("⬅️ Back to Catalog", callback_data="back_catalog")],
    ]

    await query.edit_message_text(
        text=card_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def back_to_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the chat interface back to the main catalog menu row block."""
    query = update.callback_query
    await query.answer()

    products = await fetch_products()
    if not products:
        await query.edit_message_text(
            "The catalog is currently empty or down for maintenance."
        )
        return

    reply_markup = _build_catalog_keyboard(products)
    menu_text = "📦 *Available Products*:\nSelect an item to view details:"

    await query.edit_message_text(
        text=menu_text, parse_mode="Markdown", reply_markup=reply_markup
    )
