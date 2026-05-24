import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import fetch_product_detail, fetch_products
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


def _build_catalog_keyboard(products: list) -> list:
    """Helper to format the vertical grid of catalog product buttons."""
    keyboard = []
    for item in products:
        button_text = f"{item['name']} — ${item['price']}"
        callback_data = f"view_prod_{item['id']}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )
    return keyboard


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queries the API container and renders interactive menus."""
    await clear_chat_footprint(update, context)

    products = await fetch_products()
    if not products:
        text = "The catalog is currently empty or down for maintenance."
        sent_msg = await update.effective_chat.send_message(text=text)
        context.user_data["active_menu_id"] = sent_msg.message_id
        return

    buttons = _build_catalog_keyboard(products)
    buttons.append(
        [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")]
    )
    buttons.append(
        [InlineKeyboardButton("🏠 Return to Main Menu", callback_data="back_start")]
    )

    menu_text = "📦 *Available Products*:\nSelect an item to view details:"
    sent_msg = await update.effective_chat.send_message(
        text=menu_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def view_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the deep-dive card for a specific product."""
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[-1])
    product = await fetch_product_detail(product_id)

    if not product:
        await query.edit_message_text("Product record could not be found.")
        return

    card_text = (
        f"📦 *{product['name']}*\n"
        f"Category: {product['category_name']}\n"
        f"Price: ${product['price']}\n"
        f"Stock: {product['stock']} available\n\n"
        f"_{product['description']}_"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 Add to Cart", callback_data=f"add_to_cart_{product['id']}"
            )
        ],
        [InlineKeyboardButton("🛍️ View Cart", callback_data="view_cart_nav")],
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

    buttons = _build_catalog_keyboard(products)
    buttons.append(
        [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")]
    )
    buttons.append(
        [InlineKeyboardButton("🏠 Return to Main Menu", callback_data="back_start")]
    )

    menu_text = "📦 *Available Products*:\nSelect an item to view details:"
    await query.edit_message_text(
        text=menu_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
