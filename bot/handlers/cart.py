import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import (
    add_product_to_cart,
    fetch_user_cart,
    update_item_quantity,
)
from handlers.catalog import parse_product_id
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


def parse_quantity_action(callback_data: str) -> tuple[str, int, int]:
    """Parses action, item ID, and quantity from a callback string."""
    parts = callback_data.split("_")
    return parts[1], int(parts[2]), int(parts[3])


def render_cart_menu(cart: dict) -> tuple[str, list]:
    """Generates text breakdown and controls for the shopping cart."""
    if not cart or not cart.get("items"):
        return (
            "🛒 *Your Shopping Cart is Empty.*",
            [
                [
                    InlineKeyboardButton(
                        "📦 Browse Catalog", callback_data="back_catalog"
                    )
                ]
            ],
        )

    message_lines = ["🛒 *Your Active Shopping Cart*:\n"]
    keyboard = []

    for item in cart["items"]:
        message_lines.append(
            f"• *{item['product_name']}* x{item['quantity']} — ${item['subtotal']}"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➖",
                    callback_data=f"qty_down_{item['id']}_{item['quantity']}",
                ),
                InlineKeyboardButton(
                    f"{item['product_name']}",
                    callback_data=f"view_prod_{item['product']}",
                ),
                InlineKeyboardButton(
                    "➕",
                    callback_data=f"qty_up_{item['id']}_{item['quantity']}",
                ),
            ]
        )

    message_lines.append(f"\n*Total Amount*: ${cart['cart_total']}")

    keyboard.append(
        [InlineKeyboardButton("💳 Proceed to Checkout", callback_data="checkout")]
    )
    keyboard.append(
        [InlineKeyboardButton("📦 Keep Shopping", callback_data="back_catalog")]
    )

    return "\n".join(message_lines), keyboard


async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes selections to append or increment products in the cart."""
    query = update.callback_query
    tg_id = query.from_user.id

    product_id = parse_product_id(query.data)

    success = await add_product_to_cart(tg_id, product_id)
    if success:
        await query.answer(text="🛒 Added to cart!", show_alert=False)
    else:
        await query.answer(
            text="Could not modify cart. Verify stock bounds.", show_alert=True
        )


async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes /cart or navigation to map the user cart menu."""
    query = update.callback_query
    tg_id = update.effective_user.id

    if query:
        await query.answer()
    else:
        await clear_chat_footprint(update, context)

    cart = await fetch_user_cart(tg_id)
    text, keyboard = render_cart_menu(cart)
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.edit_text(
            text, parse_mode="Markdown", reply_markup=markup
        )
    else:
        sent_msg = await update.effective_chat.send_message(
            text, parse_mode="Markdown", reply_markup=markup
        )
        context.user_data["active_menu_id"] = sent_msg.message_id


async def adjust_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alters item records incrementally down or up via click tracking flags."""
    query = update.callback_query
    await query.answer()

    action, item_id, current_qty = parse_quantity_action(query.data)
    new_qty = current_qty + 1 if action == "up" else current_qty - 1

    await update_item_quantity(item_id, new_qty)
    cart = await fetch_user_cart(update.effective_user.id)
    text, keyboard = render_cart_menu(cart)
    await query.message.edit_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
