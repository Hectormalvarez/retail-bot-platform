"""Checkout flow with address capture and order confirmation."""

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
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_ADDRESS, CONFIRMING = range(2)


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


def render_order_receipt(order_data: dict, address: str) -> tuple[str, list]:
    """Generates the completed order receipt text after checkout succeeds."""
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
    text_body = "\n".join(receipt_lines)
    return text_body, []


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
                [[InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")]]
            ),
        )
        return ConversationHandler.END

    await query.edit_message_text("📍 Please enter your full shipping address:")
    return WAITING_FOR_ADDRESS


async def capture_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address_text = update.message.text
    context.user_data["checkout_address"] = address_text
    tg_id = update.effective_user.id

    await clear_chat_footprint(update, context)

    ctx: BotContext = context.application.bot_data["ctx"]
    cart = await ctx.api.fetch_user_cart(tg_id)
    text_body, keyboard = render_order_confirmation(cart, address_text)
    sent_msg = await update.effective_chat.send_message(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["active_menu_id"] = sent_msg.message_id
    return CONFIRMING


async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    address_text = context.user_data.get("checkout_address", "N/A")
    ctx: BotContext = context.application.bot_data["ctx"]
    order_data = await ctx.api.submit_order(tg_id, address_text)

    try:
        await query.message.delete()
    except Exception:
        pass
    context.user_data["active_menu_id"] = None

    if not order_data:
        await update.effective_chat.send_message(
            text=(
                "❌ *Checkout Failed*\nYour items could not be processed. "
                "This may be due to insufficient stock or a network error."
            ),
            parse_mode="Markdown",
        )
        context.user_data.pop("checkout_address", None)
        return ConversationHandler.END

    text_body, _ = render_order_receipt(order_data, address_text)
    await update.effective_chat.send_message(text=text_body, parse_mode="Markdown")

    context.user_data.pop("checkout_address", None)
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
    return ConversationHandler.END


async def cancel_command_fallback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await clear_chat_footprint(update, context)

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
        entry_points=[
            CallbackQueryHandler(start_checkout, pattern=r"^checkout$")
        ],
        states={
            WAITING_FOR_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, capture_address
                )
            ],
            CONFIRMING: [
                CallbackQueryHandler(
                    finalize_order,
                    pattern=r"^confirm_checkout$",
                ),
                CallbackQueryHandler(
                    cancel_checkout, pattern=r"^cancel_checkout$"
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command_fallback)],
        allow_reentry=True,
    )
    app.add_handler(checkout_conv)