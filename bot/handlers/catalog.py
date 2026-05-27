"""Product catalog browsing via inline keyboards."""

from __future__ import annotations

import asyncio
import logging
import math

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


def render_catalog_menu(
    products: list,
    categories: list,
    page: int = 1,
    current_cat_id: int = 0,
    show_cats: bool = False,
) -> tuple[str, list]:
    """Generates the text body and inline keyboard markup for the catalog."""
    if show_cats:
        text = "🗂 *Select a Category:*"
        keyboard = []
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🟢 All" if current_cat_id == 0 else "All",
                    callback_data="nav_cat_0_p_1",
                )
            ]
        )

        # Chunk categories into rows of 2
        row = []
        for cat in categories:
            prefix = "🟢 " if current_cat_id == cat["id"] else ""
            row.append(
                InlineKeyboardButton(
                    f"{prefix}{cat['name']}", callback_data=f"nav_cat_{cat['id']}_p_1"
                )
            )
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ Back to Catalog", callback_data=f"nav_cat_{current_cat_id}_p_1"
                )
            ]
        )
        return text, keyboard

    items_per_page = 5
    total_pages = max(1, math.ceil(len(products) / items_per_page))
    page = max(1, min(page, total_pages))  # clamp

    cat_name = (
        next((c["name"] for c in categories if c["id"] == current_cat_id), "All")
        if current_cat_id != 0
        else "All"
    )
    text = (
        f"📦 *Available Products*\n"
        f"Viewing: {cat_name} | Page {page} of {total_pages}\n"
        f"Select an item to view details:"
    )

    keyboard = []

    # Category Filter Row
    cat_buttons = [
        InlineKeyboardButton(
            "🟢 All" if current_cat_id == 0 else "All", callback_data="nav_cat_0_p_1"
        )
    ]

    if len(categories) > 3:
        has_more = True
        default_cats = categories[:2]

        # Show defaults if no category selected or already in the top 2.
        if current_cat_id == 0 or current_cat_id in [c["id"] for c in default_cats]:
            visible_cats = default_cats
        else:
            # Swap the second slot for the currently active category
            current_cat = next(
                (c for c in categories if c["id"] == current_cat_id), None
            )
            if current_cat:
                visible_cats = [default_cats[0], current_cat]
            else:
                visible_cats = default_cats
    else:
        visible_cats = categories
        has_more = False

    for cat in visible_cats:
        prefix = "🟢 " if current_cat_id == cat["id"] else ""
        cat_buttons.append(
            InlineKeyboardButton(
                f"{prefix}{cat['name']}", callback_data=f"nav_cat_{cat['id']}_p_1"
            )
        )

    if has_more:
        cat_buttons.append(
            InlineKeyboardButton("More 🔽", callback_data=f"more_cats_{current_cat_id}")
        )

    if cat_buttons:
        keyboard.append(cat_buttons)

    # Products slice
    start_idx = (page - 1) * items_per_page
    for p in products[start_idx : start_idx + items_per_page]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{p['name']} — ${p['price']}", callback_data=f"view_prod_{p['id']}"
                )
            ]
        )

    # Pagination Controls
    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                "⬅️ Prev", callback_data=f"nav_cat_{current_cat_id}_p_{page - 1}"
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                "Next ➡️", callback_data=f"nav_cat_{current_cat_id}_p_{page + 1}"
            )
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.extend(
        [
            [InlineKeyboardButton("🛍️ View Your Cart", callback_data="view_cart_nav")],
            [
                InlineKeyboardButton(
                    "🏠 Return to Main Menu", callback_data="back_start"
                )
            ],
        ]
    )
    return text, keyboard


def render_product_card(product: dict, cart: dict | None = None) -> tuple[str, list]:
    """Generates the text body and inline keyboard for a product card.

    When *cart* is provided, the function checks whether the product is
    already in the cart and adjusts the primary button text accordingly.
    """
    if not product:
        return "Product record could not be found.", []

    # Compute dynamic stock based on active cart selections
    in_cart_qty = 0
    if cart is not None and cart.get("items"):
        for item in cart["items"]:
            if item.get("product") == product["id"]:
                in_cart_qty = item.get("quantity", 0)
                break

    display_stock = max(0, product["stock"] - in_cart_qty)

    card_text = (
        f"📦 *{product['name']}*\n"
        f"Category: {product['category_name']}\n"
        f"Price: ${product['price']}\n"
        f"Stock: {display_stock} available\n\n"
        f"_{product['description']}_"
    )

    # Determine button label based on cart presence and stock availability
    if display_stock <= 0:
        button_text = f"❌ Out of Stock ({in_cart_qty} in Cart)"
    elif in_cart_qty > 0:
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


async def navigate_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /catalog command and paginated inline navigation."""
    query = update.callback_query

    cat_id = 0
    page = 1
    show_cats = False

    if query and query.data.startswith("nav_cat_"):
        parts = query.data.split("_")
        cat_id = int(parts[2])
        page = int(parts[4])
        await query.answer()
    elif query and query.data.startswith("more_cats_"):
        cat_id = int(query.data.split("_")[2])
        show_cats = True
        await query.answer()
    elif query and query.data == "back_catalog":
        await query.answer()
    else:
        await clear_chat_footprint(update, context)

    ctx: BotContext = context.application.bot_data["ctx"]

    api_cat_id = cat_id if cat_id != 0 else None
    products, categories = await asyncio.gather(
        ctx.api.fetch_products(category_id=api_cat_id), ctx.api.fetch_categories()
    )

    text, keyboard = render_catalog_menu(products, categories, page, cat_id, show_cats)
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if query:
        try:
            await query.edit_message_text(
                text=text, parse_mode="Markdown", reply_markup=markup
            )
        except BadRequest as exc:
            if "Message is not modified" in exc.message:
                pass
            else:
                raise
    else:
        sent_msg = await update.effective_chat.send_message(
            text=text, parse_mode="Markdown", reply_markup=markup
        )
        context.user_data["active_menu_id"] = sent_msg.message_id


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
    app.add_handler(CommandHandler("catalog", navigate_catalog))
    app.add_handler(
        CallbackQueryHandler(navigate_catalog, pattern=r"^nav_cat_\d+_p_\d+$")
    )
    app.add_handler(CallbackQueryHandler(navigate_catalog, pattern=r"^back_catalog$"))
    app.add_handler(CallbackQueryHandler(navigate_catalog, pattern=r"^more_cats_\d+$"))
    app.add_handler(
        CallbackQueryHandler(view_product_detail, pattern=r"^view_prod_\d+$")
    )
