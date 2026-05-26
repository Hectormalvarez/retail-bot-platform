import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import fetch_product_detail, fetch_products
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


def parse_product_id(callback_data: str) -> int:
    """Extracts the integer product database ID from a callback query string."""
    return int(callback_data.split("_")[-1])


def render_catalog_menu(products: list) -> tuple[str, list]:
    """Generates the text body and inline keyboard markup for the catalog."""
    if not products:
        return "The catalog is currently empty or down for maintenance.", []

    keyboard = [
        [
            InlineKeyboardButton(
                f"{p['name']} — ${p['price']}",
                callback_data=f"view_prod_{p['id']}",
            )
        ]
        for p in products
    ]
    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "🛍️ View Your Cart", callback_data="view_cart_nav"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Return to Main Menu", callback_data="back_start"
                )
            ],
        ]
    )
    return "📦 *Available Products*:\nSelect an item to view details:", keyboard


def render_product_card(product: dict) -> tuple[str, list]:
    """Generates the text body and inline keyboard for a product card."""
    if not product:
        return "Product record could not be found.", []

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
        [
            InlineKeyboardButton(
                "⬅️ Back to Catalog", callback_data="back_catalog"
            )
        ],
    ]
    return card_text, keyboard


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes /catalog command to fetch and display available store items."""
    await clear_chat_footprint(update, context)
    products = await fetch_products()

    text, keyboard = render_catalog_menu(products)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    sent_msg = await update.effective_chat.send_message(
        text=text, parse_mode="Markdown", reply_markup=markup
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def view_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callback interactions to display full item specifications."""
    query = update.callback_query
    await query.answer()

    product_id = parse_product_id(query.data)
    product = await fetch_product_detail(product_id)

    text, keyboard = render_product_card(product)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await query.edit_message_text(
        text=text, parse_mode="Markdown", reply_markup=markup
    )


async def back_to_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles navigation callback requests to return users to the catalog."""
    query = update.callback_query
    await query.answer()

    products = await fetch_products()
    text, keyboard = render_catalog_menu(products)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await query.edit_message_text(
        text=text, parse_mode="Markdown", reply_markup=markup
    )