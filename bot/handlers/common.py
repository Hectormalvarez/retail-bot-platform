"""Welcome / start dashboard and shared utilities."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from context import BotContext

logger = logging.getLogger(__name__)


# ---- helpers (no DI needed – pure functions) ---------------------------

_ORDER_STATUS_LABELS = {
    "PENDING": "Pending Payment",
    "COMPLETED": "Completed/Paid",
    "SHIPPED": "Shipped",
    "CANCELLED": "Cancelled",
}


def render_orders_history(
    orders: list[dict],
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Render the order history menu text and inline keyboard layout.

    This is a pure function with no I/O side effects.

    Parameters
    ----------
    orders : list[dict]
        The user's past orders. Each dict should have at least
        ``{"id": int, "total_amount": str}``.

    Returns
    -------
    tuple[str, list[list[InlineKeyboardButton]]]
        The formatted menu text and the inline keyboard grid.
    """
    if not orders:
        text_body = "📜 *You don't have any past orders yet.*"
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_start")],
        ]
        return text_body, keyboard

    text_body = (
        "📜 *Your Purchase History*\n"
        "Select an order below to view its full receipt and "
        "cash-payment verification status:"
    )

    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                f"📦 Order #{o['id']} — ${o['total_amount']} ({o['status'].title()})",
                callback_data=f"view_old_order_{o['id']}",
            )
        ]
        for o in orders
    ]
    keyboard.append(
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_start")]
    )

    return text_body, keyboard


def render_welcome_dashboard(
    user_name: str,
    cart: dict | None,
    latest_order: dict | None,
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Render the welcome dashboard text and inline keyboard layout.

    This is a pure function with no I/O side effects. It produces a message
    body string and a raw keyboard grid that the caller can wrap with
    InlineKeyboardMarkup.

    Parameters
    ----------
    user_name : str
        The display name of the user.
    cart : dict or None
        The user's active cart dict, or None if no cart exists.
        Expected shape: {"items": [...], "cart_total": "XX.XX"}.
    latest_order : dict or None
        The user's most recent order dict, or None if no orders exist.
        Expected shape: {"id": int, "status": str}.

    Returns
    -------
    tuple[str, list[list[InlineKeyboardButton]]]
        The formatted welcome message and the inline keyboard grid.
    """
    text_parts = [f"Welcome back, {user_name}!"]

    # ---- Cart section ---------------------------------------------------
    if cart is None or not cart.get("items"):
        text_parts.append("🛒 Your cart is empty")
    else:
        total_items = sum(item["quantity"] for item in cart["items"])
        cart_total = cart["cart_total"]
        text_parts.append(f"🛒 Active Cart: {total_items} items (${cart_total})")

    # ---- Order tracking section -----------------------------------------
    if latest_order is None:
        text_parts.append("📦 No recent orders")
    else:
        order_id = latest_order["id"]
        status_code = latest_order["status"]
        status_label = _ORDER_STATUS_LABELS.get(status_code, status_code)
        text_parts.append(f"📦 Order #{order_id}: [{status_label}]")

    text_body = "\n".join(text_parts)

    # ---- Keyboard layout ------------------------------------------------
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📦 Browse Catalog", callback_data="back_catalog")],
    ]

    # Row 2: View Active Cart (only if cart has items)
    if cart is not None and cart.get("items"):
        keyboard.append(
            [InlineKeyboardButton("🛍️ View Active Cart", callback_data="view_cart_nav")]
        )

    # Row 3: Order History (only if latest_order exists)
    if latest_order is not None:
        keyboard.append(
            [InlineKeyboardButton("📜 Order History", callback_data="view_history_nav")]
        )

    return text_body, keyboard


def extract_user_context(update: Update) -> dict:
    """Helper to cleanly extract Telegram user metadata."""
    user = update.effective_user
    return {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


async def clear_chat_footprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Evicts incoming text triggers and deletes the stale menu canvas."""
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    last_menu_id = context.user_data.get("active_menu_id")
    if last_menu_id:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=last_menu_id
            )
        except Exception as exc:
            logger.debug("Stale menu message already cleared: %s", exc)

        context.user_data["active_menu_id"] = None


# ---- handlers -----------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user, syncs profile data, and initiates a clean dashboard.

    Uses :func:`render_welcome_dashboard` to produce the message and
    keyboard based on live cart / order state fetched concurrently from
    the API.  The edit/heal loop ensures the dashboard canvas is always
    correctly positioned in the chat timeline.
    """
    # 1. Footprint eviction – delete the raw /start text from the timeline
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    # 2. Gather identity
    tg_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # 3. Concurrent data fetching
    ctx: BotContext = context.application.bot_data["ctx"]
    user_ctx = extract_user_context(update)
    cart, orders = await asyncio.gather(
        ctx.api.fetch_user_cart(tg_id),
        ctx.api.fetch_user_orders(tg_id),
    )

    # 4. Sync user profile (fire-and-forget from the caller's perspective)
    await ctx.api.sync_user(user_ctx)

    # 5. Parse latest order
    latest_order = orders[0] if orders else None

    # 6. Build dashboard content (pure function)
    text_body, keyboard = render_welcome_dashboard(
        user_name,
        cart,
        latest_order,
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 7. Self-healing edit loop
    active_menu_id = context.user_data.get("active_menu_id")
    if active_menu_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=active_menu_id,
                text=text_body,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            # Canvas was deleted / expired – fall through to send_message
            pass

    sent_msg = await update.effective_chat.send_message(
        text=text_body,
        reply_markup=reply_markup,
    )
    context.user_data["active_menu_id"] = sent_msg.message_id


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the chat interface back to the main welcome menu canvas."""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    user_name = query.from_user.first_name

    ctx: BotContext = context.application.bot_data["ctx"]
    cart, orders = await asyncio.gather(
        ctx.api.fetch_user_cart(tg_id),
        ctx.api.fetch_user_orders(tg_id),
    )
    latest_order = orders[0] if orders else None

    text_body, keyboard = render_welcome_dashboard(
        user_name,
        cart,
        latest_order,
    )
    await query.edit_message_text(
        text=text_body,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---- registration -------------------------------------------------------


def register_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", start))  # legacy alias – main menu
    app.add_handler(CommandHandler("cancel", start))  # fallback command
    app.add_handler(CallbackQueryHandler(back_to_start, pattern=r"^back_start$"))
