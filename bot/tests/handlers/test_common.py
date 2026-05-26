from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.common import (
    back_to_start,
    clear_chat_footprint,
    render_welcome_dashboard,
    start,
)


# ---- pure helpers (no DI needed) ----------------------------------------


@pytest.mark.asyncio
async def test_clear_chat_footprint_deletes_stale_menu():
    update = MagicMock()
    update.message = None
    update.effective_chat.id = 12345

    context = MagicMock()
    context.user_data = {"active_menu_id": 999}
    context.bot.delete_message = AsyncMock()

    await clear_chat_footprint(update, context)

    context.bot.delete_message.assert_called_once_with(
        chat_id=12345, message_id=999
    )
    assert context.user_data["active_menu_id"] is None


@pytest.mark.asyncio
async def test_clear_chat_footprint_ignores_missing_menu():
    update = MagicMock()
    update.message = None

    context = MagicMock()
    context.user_data = {}
    context.bot.delete_message = AsyncMock()

    await clear_chat_footprint(update, context)

    context.bot.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_clear_chat_footprint_handles_delete_exception():
    """When delete_message raises, the exception is caught and logged."""
    update = MagicMock()
    update.message = None
    update.effective_chat.id = 12345

    context = MagicMock()
    context.user_data = {"active_menu_id": 999}
    context.bot.delete_message = AsyncMock(side_effect=Exception("not found"))

    await clear_chat_footprint(update, context)

    # Should not raise, and user_data should still be cleared
    assert context.user_data["active_menu_id"] is None


# ---- render_welcome_dashboard (pure – no DI, no asyncio) ----------------


def test_render_welcome_dashboard_pristine_user():
    """Scenario 1: A pristine user with no cart and no orders."""
    text, keyboard = render_welcome_dashboard(
        user_name="Alice",
        cart=None,
        latest_order=None,
    )

    # Text assertions
    assert "Your cart is empty" in text
    assert "No recent orders" in text
    assert "Welcome back, Alice!" in text

    # Keyboard assertions
    assert len(keyboard) == 1  # only Browse Catalog row
    assert keyboard[0][0].text == "📦 Browse Catalog"
    assert keyboard[0][0].callback_data == "back_catalog"


def test_render_welcome_dashboard_with_active_cart():
    """Scenario 2: A user with an active cart (no orders)."""
    sample_cart = {
        "items": [
            {"product_name": "Widget A", "quantity": 2, "subtotal": "19.98"},
            {"product_name": "Widget B", "quantity": 1, "subtotal": "9.99"},
            {"product_name": "Widget C", "quantity": 3, "subtotal": "44.97"},
        ],
        "cart_total": "74.94",
    }

    text, keyboard = render_welcome_dashboard(
        user_name="Bob",
        cart=sample_cart,
        latest_order=None,
    )

    # Text assertions: total_items should be 2 + 1 + 3 = 6
    assert "Active Cart: 6 items ($74.94)" in text
    assert "No recent orders" in text

    # Keyboard assertions: Browse Catalog + View Active Cart
    assert len(keyboard) == 2
    assert keyboard[0][0].text == "📦 Browse Catalog"
    assert keyboard[1][0].text == "🛍️ View Active Cart"
    assert keyboard[1][0].callback_data == "view_cart_nav"


def test_render_welcome_dashboard_with_shipped_order():
    """Scenario 3: A user with a shipped order (no active cart)."""
    sample_order = {
        "id": 42,
        "status": "SHIPPED",
    }

    text, keyboard = render_welcome_dashboard(
        user_name="Charlie",
        cart=None,
        latest_order=sample_order,
    )

    # Text assertions
    assert "Your cart is empty" in text
    assert "Order #42" in text
    assert "[Shipped]" in text

    # Keyboard assertions: Browse Catalog + Order History
    assert len(keyboard) == 2
    assert keyboard[0][0].text == "📦 Browse Catalog"
    assert keyboard[1][0].text == "📜 Order History"
    assert keyboard[1][0].callback_data == "view_history_nav"


# ---- start / back_to_start (need app.bot_data["ctx"]) -------------------


@pytest.mark.asyncio
async def test_start_command_renders_menu(context_with_app):
    """start() syncs user and sends a welcome message."""
    context_with_app.user_data = {}

    update = MagicMock()
    update.effective_user.id = 123
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 404
    update.message = None

    await start(update, context_with_app)

    update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 404
    ctx = context_with_app.application.bot_data["ctx"]
    assert 123 in ctx.api.users


@pytest.mark.asyncio
async def test_back_to_start_edits_message():
    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    await back_to_start(update, context)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()

    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "Welcome to the Retail Bot!" in call_args["text"]