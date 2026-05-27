"""Shopping cart management via inline keyboards."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from context import BotContext
from handlers.catalog import parse_product_id, render_product_card
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


# ---- pure helpers (no DI) -----------------------------------------------


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
                    ),
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


# ---- handlers ------------------------------------------------------------


async def add_to_cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes selections to append or increment products in the cart, enforcing inventory bounds."""
    query = update.callback_query
    tg_id = query.from_user.id

    product_id = parse_product_id(query.data)
    ctx: BotContext = context.application.bot_data["ctx"]

    # Gather current layout baselines to evaluate limits defensively
    product, cart = await asyncio.gather(
        ctx.api.fetch_product_detail(product_id),
        ctx.api.fetch_user_cart(tg_id),
    )

    in_cart_qty = 0
    if cart and cart.get("items"):
        in_cart_qty = next(
            (i["quantity"] for i in cart["items"] if i["product"] == product_id), 0
        )

    if product and in_cart_qty >= product["stock"]:
        await query.answer(
            text="⚠️ Cannot add more. Physical stock limit reached!", show_alert=True
        )
        return

    success = await ctx.api.add_product_to_cart(tg_id, product_id)
    if success:
        await query.answer(text="🛒 Added to cart!", show_alert=False)

        # Re-fetch fresh metrics to update canvas state
        fresh_product, fresh_cart = await asyncio.gather(
            ctx.api.fetch_product_detail(product_id),
            ctx.api.fetch_user_cart(tg_id),
        )
        text, keyboard = render_product_card(fresh_product, fresh_cart)

        try:
            await query.message.edit_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as exc:
            logger.debug("Idempotent screen redraw skipped: %s", exc)
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

    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(tg_id)
    text, keyboard = render_cart_menu(cart)
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)
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

    ctx: BotContext = context.application.bot_data["ctx"]
    await ctx.api.update_item_quantity(item_id, new_qty)

    cart = await ctx.api.fetch_user_cart(update.effective_user.id)
    text, keyboard = render_cart_menu(cart)
    await query.message.edit_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---- registration --------------------------------------------------------


def register_handlers(app) -> None:
    app.add_handler(CommandHandler("cart", cart_command))
    app.add_handler(CallbackQueryHandler(cart_command, pattern=r"^view_cart_nav$"))
    app.add_handler(
        CallbackQueryHandler(add_to_cart_handler, pattern=r"^add_to_cart_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(
            adjust_quantity_handler, pattern=r"^qty_(up|down)_\d+_\d+$"
        )
    )
