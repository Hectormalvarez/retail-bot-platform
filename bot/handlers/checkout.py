import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from api_client import fetch_user_cart
from handlers.common import clear_chat_footprint

logger = logging.getLogger(__name__)

WAITING_FOR_ADDRESS, CONFIRMING = range(2)


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    cart = await fetch_user_cart(tg_id)
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

    await query.edit_message_text("📍 Please enter your full shipping address:")
    return WAITING_FOR_ADDRESS


async def capture_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address_text = update.message.text
    context.user_data["checkout_address"] = address_text
    tg_id = update.effective_user.id

    await clear_chat_footprint(update, context)

    cart = await fetch_user_cart(tg_id)
    message_lines = [
        "💳 *Confirm Your Order Selection*:\n",
        f"📍 *Shipping To*:\n`{address_text}`\n",
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

    sent_msg = await update.effective_chat.send_message(
        text=text_body,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["active_menu_id"] = sent_msg.message_id
    return CONFIRMING


async def finalize_order_placeholder(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id

    cart = await fetch_user_cart(tg_id)
    address_text = context.user_data.get("checkout_address", "N/A")

    try:
        await query.message.delete()
    except Exception:
        pass
    context.user_data["active_menu_id"] = None

    receipt_lines = [
        "✅ *Order Confirmed*\n",
        f"*Shipping Address*:\n`{address_text}`\n",
        "*Items*:",
    ]

    if cart and "items" in cart:
        for item in cart["items"]:
            receipt_lines.append(
                f"• {item['product_name']} x{item['quantity']} — ${item['subtotal']}"
            )
        receipt_lines.append(f"\n*Total Paid*: ${cart['cart_total']}")
    else:
        receipt_lines.append("\n_Processing transaction items._")

    text_body = "\n".join(receipt_lines)

    await update.effective_chat.send_message(text=text_body, parse_mode="Markdown")
    
    context.user_data.pop("checkout_address", None)
    return ConversationHandler.END


async def cancel_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer(text="Checkout aborted.")

    from handlers.cart import cart_command

    await cart_command(update, context)
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
