"""Checkout flow with saved address selection and address save prompt."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from context import BotContext
from handlers.cart import render_cart_menu
from handlers.common import clear_chat_footprint, render_orders_history

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ADDRESS, WAITING_FOR_ADDRESS, ASK_SAVE_ADDRESS, CONFIRMING = range(4)


# ---- pure render helpers (no DI) ----------------------------------------


def render_order_confirmation(cart: dict, address: str) -> tuple[str, list]:
    """Generates the order confirmation preview text and control buttons."""
    message_lines = [
        "💳 *Confirm Your Order Selection*:\n",
        f"📍 *Shipping To*:\n`{address}`\n",
    ]
    for item in cart["items"]:
        message_lines.append(
            f"• *{item['product_name']}* x{item['quantity']} — ${item['subtotal']}"
        )

    message_lines.append(f"\n*Total Amount Due*: ${cart['cart_total']}")
    text_body = "\n".join(message_lines)

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Confirm & Place Order", callback_data="confirm_checkout"
            )
        ],
        [InlineKeyboardButton("❌ Cancel Checkout", callback_data="cancel_checkout")],
    ]
    return text_body, keyboard


def render_order_receipt(
    order_data: dict,
    address: str | dict,
    config: dict[str, str],
    back_callback: str = "back_start",
    back_label: str = "🏠 Return to Main Menu",
) -> tuple[str, list]:
    """Generates the completed order receipt text after checkout succeeds.

    Appends manual payment instructions (from DB-backed config) so the user
    knows how to pay for manually-fulfilled orders.

    Parameters
    ----------
    order_data : dict
        The order response from the API.
    address : str | dict
        The shipping address used for the order. Can be a raw string or a
        dict with a ``"raw_address"`` key.
    config : dict[str, str]
        Key-value config dict (e.g. payment handles / instructions).
    back_callback : str
        Callback data for the bottom navigation button.
        Defaults to ``back_start`` (main menu).
    back_label : str
        Label for the bottom navigation button.
        Defaults to ``"🏠 Return to Main Menu"``.

    Returns
    -------
    tuple[str, list]
        The formatted receipt text and inline keyboard grid.
    """
    # Normalize address – it may be a dict with a "raw_address" key
    if isinstance(address, dict):
        address = address.get("raw_address", "")
    else:
        address = str(address)

    receipt_lines = [
        f"✅ *Order #{order_data['id']} Confirmed*\n",
        f"*Shipping Address*:\n`{address}`\n",
        "*Items*:",
    ]

    for item in order_data["items"]:
        receipt_lines.append(
            f"• {item['product_name']} x{item['quantity']} "
            f"— ${item['price_at_purchase']}"
        )

    receipt_lines.append(f"\n*Total Paid*: ${order_data['total_amount']}")

    # Status-aware payment section
    status = order_data.get("status", "PENDING")
    if status == "PENDING":
        # Show dynamic payment instructions for unpaid orders
        payment_text = config.get("payment_instructions", "").format(
            venmo_handle=config.get("venmo_handle", ""),
            zelle_email=config.get("zelle_email", ""),
            order_id=order_data["id"],
        )
        if payment_text:
            receipt_lines.extend(["", payment_text])
    elif status in ("COMPLETED", "SHIPPED"):
        # Show Payment Received badge for paid/shipped orders
        receipt_lines.extend(["", "✅ *Payment Received*"])

    text_body = "\n".join(receipt_lines)

    keyboard = [
        [InlineKeyboardButton(back_label, callback_data=back_callback)],
    ]
    return text_body, keyboard


def build_address_keyboard(
    addresses: list[dict],
) -> list[list[InlineKeyboardButton]]:
    """Build inline keyboard from saved addresses."""
    keyboard = []
    for addr in addresses:
        label = addr["label"]
        preview = addr["full_address"][:40]
        button_text = f"📍 {label}: {preview}..."
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f"pick_addr_{addr['id']}")]
        )
    keyboard.append(
        [InlineKeyboardButton("➕ Enter New Address", callback_data="new_address")]
    )
    keyboard.append(
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_checkout")]
    )
    return keyboard


def compute_address_label(addresses: list[dict]) -> str:
    """Generate a label like 'Address #1' based on existing address count."""
    return f"Address #{len(addresses) + 1}"


async def view_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the "View Order History" callback button and pagination.

    Fetches the user's past orders from the API and renders an order history
    menu using the pure :func:`render_orders_history` presenter.

    Parses the requested page from ``query.data``:
    - ``view_history_nav`` → page 1
    - ``view_history_p_X`` → page X
    """
    query = update.callback_query
    await query.answer()

    # Parse the page number from callback data
    data = query.data
    if data == "view_history_nav":
        page = 1
    elif data.startswith("view_history_p_"):
        page = int(data.split("_")[-1])
    else:
        page = 1

    tg_id = query.from_user.id
    ctx: BotContext = context.application.bot_data["ctx"]
    orders = await ctx.api.fetch_user_orders(tg_id)

    text_body, keyboard = render_orders_history(orders, page=page)
    await query.edit_message_text(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


async def view_historical_order_detail_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handles a click on a past order row in the history list.

    Extracts the historical order ID from the callback data, fetches the
    user's full order list, finds the matching order, and renders the
    receipt with a ``[⬅️ Back to History]`` navigation button.
    """
    query = update.callback_query
    await query.answer()

    # Extract order ID from callback like "view_old_order_42"
    historical_order_id = int(query.data.split("_")[-1])

    tg_id = query.from_user.id
    ctx: BotContext = context.application.bot_data["ctx"]
    orders = await ctx.api.fetch_user_orders(tg_id)

    # Find the matching order
    order = next(
        (o for o in orders if o["id"] == historical_order_id),
        None,
    )
    if order is None:
        await query.edit_message_text(
            "❌ Order not found. It may have been removed.",
        )
        return

    config = await ctx.api.fetch_store_config()
    address = order.get("shipping_address", "Unknown")
    text_body, keyboard = render_order_receipt(
        order,
        address,
        config,
        back_callback="view_history_nav",
        back_label="⬅️ Back to History",
    )
    await query.edit_message_text(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---- handlers ------------------------------------------------------------


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(tg_id)
    if not cart or not cart["items"]:
        await query.edit_message_text(
            "🛒 Your cart is empty! Add items before checking out.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📦 Browse Catalog", callback_data="back_catalog"
                        )
                    ]
                ]
            ),
        )
        return ConversationHandler.END

    # Fetch saved addresses
    addresses = await ctx.api.fetch_addresses(tg_id)
    context.user_data["saved_addresses"] = addresses

    if addresses:
        keyboard = build_address_keyboard(addresses)
        await query.edit_message_text(
            "📍 *Choose a shipping address:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return SELECTING_ADDRESS
    else:
        # No saved addresses — go straight to text input
        await query.edit_message_text("📍 Please enter your full shipping address:")
        return WAITING_FOR_ADDRESS


async def pick_saved_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Extract address_id from callback data like "pick_addr_1"
    address_id = int(query.data.split("_")[-1])
    addresses: list[dict] = context.user_data.get("saved_addresses", [])
    selected = next((a for a in addresses if a["id"] == address_id), None)
    if not selected:
        await query.edit_message_text(
            "❌ Address not found. Please try again.",
        )
        return ConversationHandler.END

    address_text = selected["full_address"]
    context.user_data["checkout_address"] = address_text
    context.user_data["address_was_saved"] = True

    tg_id = query.from_user.id
    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(tg_id)
    text_body, keyboard = render_order_confirmation(cart, address_text)
    await query.edit_message_text(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


async def prompt_new_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📍 Please enter your full shipping address:")
    return WAITING_FOR_ADDRESS


async def capture_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address_text = update.message.text
    context.user_data["checkout_address"] = address_text
    context.user_data["address_was_saved"] = False

    await clear_chat_footprint(update, context)

    # Ask if they want to save this address
    keyboard = [
        [InlineKeyboardButton("💾 Save for future use", callback_data="save_addr_yes")],
        [InlineKeyboardButton("❌ Don't save", callback_data="save_addr_no")],
    ]
    sent_msg = await update.effective_chat.send_message(
        text=(
            "📍 *Address received:*\n"
            f"`{address_text}`\n\n"
            "💾 Would you like to save this address for future checkouts?"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["active_menu_id"] = sent_msg.message_id
    return ASK_SAVE_ADDRESS


async def save_address_and_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    address_text = context.user_data.get("checkout_address", "")

    ctx: BotContext = context.application.bot_data["ctx"]
    # Count existing addresses to generate label
    addresses = await ctx.api.fetch_addresses(tg_id)
    label = compute_address_label(addresses)
    await ctx.api.create_address(tg_id, label, address_text)
    context.user_data["address_was_saved"] = True

    cart = await ctx.api.fetch_user_cart(tg_id)
    text_body, keyboard = render_order_confirmation(cart, address_text)
    await query.edit_message_text(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


async def skip_save_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    address_text = context.user_data.get("checkout_address", "")

    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(tg_id)
    text_body, keyboard = render_order_confirmation(cart, address_text)
    await query.edit_message_text(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRMING


async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    cbq_id = query.id
    if context.user_data.get("_last_cbq_id") == cbq_id:
        logger.debug("Duplicate callback query ignored: %s", cbq_id)
        return ConversationHandler.END
    context.user_data["_last_cbq_id"] = cbq_id

    tg_id = query.from_user.id

    address_text = context.user_data.get("checkout_address", "N/A")
    ctx: BotContext = context.application.bot_data["ctx"]
    order_data = await ctx.api.submit_order(tg_id, address_text)
    config = await ctx.api.fetch_store_config()

    if not order_data:
        failure_text = (
            "❌ *Checkout Failed*\nYour items could not be processed. "
            "This may be due to insufficient stock or a network error."
        )
        failure_keyboard = [
            [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_start")],
        ]
        try:
            await query.edit_message_text(
                text=failure_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(failure_keyboard),
            )
        except Exception as exc:
            logger.debug("Failure screen redraw skipped: %s", exc)

        context.user_data.pop("checkout_address", None)
        context.user_data.pop("address_was_saved", None)
        context.user_data.pop("saved_addresses", None)
        context.user_data.pop("active_menu_id", None)
        return ConversationHandler.END

    text_body, keyboard = render_order_receipt(order_data, address_text, config)

    try:
        await query.edit_message_text(
            text=text_body,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as exc:
        logger.debug("Receipt screen redraw skipped: %s", exc)

    cleanup_checkout_state(context)
    return ConversationHandler.END


def cleanup_checkout_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove all checkout-related keys from user_data.

    Called by every conversation exit path (timeout, cancel, /cancel command,
    and successful finalization) so stale state never leaks into a fresh
    checkout attempt.
    """
    for key in (
        "checkout_address",
        "address_was_saved",
        "saved_addresses",
        "active_menu_id",
    ):
        context.user_data.pop(key, None)


async def timeout_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle ConversationHandler timeout — notify the user and clean up."""
    cleanup_checkout_state(context)

    if update.effective_chat is not None:
        await update.effective_chat.send_message(
            "⏰ *Checkout session expired.*\n"
            "Your cart is still saved — use /cart to continue shopping.",
            parse_mode="Markdown",
        )
    return ConversationHandler.END


async def cancel_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer(text="Checkout aborted.")

    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(query.from_user.id)
    text, keyboard = render_cart_menu(cart)
    await query.message.edit_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    cleanup_checkout_state(context)
    return ConversationHandler.END


async def cancel_command_fallback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await clear_chat_footprint(update, context)
    cleanup_checkout_state(context)

    text = "❌ Checkout wizard dropped. Returning to main menu dashboard."
    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_start")]]

    sent_msg = await update.effective_chat.send_message(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data["active_menu_id"] = sent_msg.message_id
    return ConversationHandler.END


# ---- registration --------------------------------------------------------


def register_handlers(app) -> None:
    checkout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_checkout, pattern=r"^checkout$")],
        states={
            SELECTING_ADDRESS: [
                CallbackQueryHandler(
                    pick_saved_address,
                    pattern=r"^pick_addr_\d+$",
                ),
                CallbackQueryHandler(prompt_new_address, pattern=r"^new_address$"),
                CallbackQueryHandler(cancel_checkout, pattern=r"^cancel_checkout$"),
            ],
            WAITING_FOR_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, capture_address)
            ],
            ASK_SAVE_ADDRESS: [
                CallbackQueryHandler(
                    save_address_and_confirm,
                    pattern=r"^save_addr_yes$",
                ),
                CallbackQueryHandler(
                    skip_save_confirm,
                    pattern=r"^save_addr_no$",
                ),
            ],
            CONFIRMING: [
                CallbackQueryHandler(
                    finalize_order,
                    pattern=r"^confirm_checkout$",
                ),
                CallbackQueryHandler(cancel_checkout, pattern=r"^cancel_checkout$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command_fallback)],
        allow_reentry=True,
        conversation_timeout=600,  # 10 minutes
        timeout_callback=timeout_checkout,
    )
    app.add_handler(
        CallbackQueryHandler(
            view_historical_order_detail_handler, pattern=r"^view_old_order_\d+$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(view_history_handler, pattern=r"^view_history_nav$")
    )
    app.add_handler(
        CallbackQueryHandler(view_history_handler, pattern=r"^view_history_p_\d+$")
    )
    app.add_handler(checkout_conv)
