"""Product catalog browsing via inline keyboards."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from context import BotContext
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)


# ---- pure helpers (no DI) -----------------------------------------------


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
            [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")],
            [
                InlineKeyboardButton(
                    "🏠 Return to Main Menu", callback_data="back_start"
                ),
            ],
        ]
    )
    return "📦 *Available Products*:\nSelect an item to view details:", keyboard


def render_product_card(product: dict, cart: dict | None = None) -> tuple[str, list]:
    """Generates the text body and inline keyboard for a product card.

    When *cart* is provided, the function checks whether the product is
    already in the cart and adjusts the primary button text accordingly.
    """
    if not product:
        return "Product record could not be found.", []

    card_text = (
        f"📦 *{product['name']}*\n"
        f"Category: {product['category_name']}\n"
        f"Price: ${product['price']}\n"
        f"Stock: {product['stock']} available\n\n"
        f"_{product['description']}_"
    )

    # Determine button label based on cart presence
    in_cart_qty = 0
    if cart is not None and cart.get("items"):
        for item in cart["items"]:
            if item.get("product") == product["id"]:
                in_cart_qty = item.get("quantity", 0)
                break

    if in_cart_qty:
        button_text = f"🛒 Add Another ({in_cart_qty} in Cart)"
    else:
        button_text = "🛒 Add to Cart"

    keyboard = [
        [
            InlineKeyboardButton(
                button_text, callback_data=f"add_to_cart_{product['id']}"
            ),
        ],
        [InlineKeyboardButton("🛍️ View Cart", callback_data="view_cart_nav")],
        [InlineKeyboardButton("⬅️ Back to Catalog", callback_data="back_catalog")],
    ]
    return card_text, keyboard


# ---- handlers ------------------------------------------------------------


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes /catalog command to fetch and display available store items."""
    await clear_chat_footprint(update, context)
    ctx: BotContext = context.application.bot_data["ctx"]
    products = await ctx.api.fetch_products()

    text, keyboard = render_catalog_menu(products)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    sent_msg = await update.effective_chat.send_message(
        text=text, parse_mode="Markdown", reply_markup=markup
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def back_to_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles navigation callback requests to return users to the catalog.

    Swallows ``BadRequest("Message is not modified")`` — the UI is already
    in the correct state so no action is needed.
    """
    query = update.callback_query
    await query.answer()

    ctx: BotContext = context.application.bot_data["ctx"]
    products = await ctx.api.fetch_products()
    text, keyboard = render_catalog_menu(products)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    try:
        await query.edit_message_text(
            text=text, parse_mode="Markdown", reply_markup=markup
        )
    except BadRequest as exc:
        if "Message is not modified" in exc.message:
            pass  # Idempotent — the canvas is already correct.
        else:
            raise


async def view_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callback interactions to display full item specifications."""
    query = update.callback_query
    await query.answer()

    product_id = parse_product_id(query.data)
    tg_id = query.from_user.id
    ctx: BotContext = context.application.bot_data["ctx"]

    # Fetch product details and cart concurrently
    product, cart = await asyncio.gather(
        ctx.api.fetch_product_detail(product_id),
        ctx.api.fetch_user_cart(tg_id),
    )

    text, keyboard = render_product_card(product, cart)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    try:
        await query.edit_message_text(
            text=text, parse_mode="Markdown", reply_markup=markup
        )
    except BadRequest as exc:
        if "Message is not modified" in exc.message:
            pass  # Idempotent — the canvas is already correct.
        else:
            raise


# ---- registration --------------------------------------------------------


def register_handlers(app) -> None:
    app.add_handler(CommandHandler("catalog", catalog_command))
    app.add_handler(
        CallbackQueryHandler(view_product_detail, pattern=r"^view_prod_\d+$")
    )
    app.add_handler(CallbackQueryHandler(back_to_catalog, pattern=r"^back_catalog$"))
