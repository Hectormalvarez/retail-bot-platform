import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from api_client import (
    add_product_to_cart,
    fetch_user_cart,
    update_item_quantity,
)
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercepts product detail clicks to register item choices."""
    query = update.callback_query
    tg_id = query.from_user.id
    product_id = int(query.data.split("_")[-1])

    success = await add_product_to_cart(tg_id, product_id)
    if success:
        await query.answer(text="🛒 Added to cart!", show_alert=False)
    else:
        await query.answer(
            text="Could not modify cart. Verify stock bounds.", show_alert=True
        )


async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders the line-by-line summary breakdown with control layers."""
    query = update.callback_query
    is_callback = query is not None
    tg_id = update.effective_user.id

    if is_callback:
        await query.answer()
    else:
        await clear_chat_footprint(update, context)

    cart = await fetch_user_cart(tg_id)
    if not cart or not cart["items"]:
        text = (
            "🛒 *Your Shopping Cart is Empty.*\n"
            "Select the option below to explore active store items."
        )
        keyboard = [
            [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_callback:
            await query.message.edit_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )
        else:
            sent_msg = await update.effective_chat.send_message(
                text=text, parse_mode="Markdown", reply_markup=reply_markup
            )
            context.user_data["active_menu_id"] = sent_msg.message_id
        return

    message_lines = ["🛒 *Your Active Shopping Cart*:\n"]
    keyboard = []

    for item in cart["items"]:
        line = f"• *{item['product_name']}* x{item['quantity']} — ${item['subtotal']}"
        message_lines.append(line)

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
    text_body = "\n".join(message_lines)

    keyboard.append(
        [InlineKeyboardButton("💳 Proceed to Checkout", callback_data="checkout")]
    )
    keyboard.append(
        [InlineKeyboardButton("📦 Keep Shopping", callback_data="back_catalog")]
    )

    if is_callback:
        await query.message.edit_text(
            text=text_body,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        sent_msg = await update.effective_chat.send_message(
            text=text_body,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        context.user_data["active_menu_id"] = sent_msg.message_id


async def adjust_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modifies line quantity counters without causing screen scroll noise."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]
    item_id = int(parts[2])
    current_qty = int(parts[3])

    new_qty = current_qty + 1 if action == "up" else current_qty - 1

    await update_item_quantity(item_id, new_qty)
    await cart_command(update, context)
