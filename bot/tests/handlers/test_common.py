from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.common import (
    back_to_start,
    clear_chat_footprint,
    render_orders_history,
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

    context.bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
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


# ---- render_orders_history (pure – no DI, no asyncio) ------------------


def test_render_orders_history_no_orders():
    """Empty orders list returns 'no orders' with Browse Catalog + Back."""
    text, keyboard = render_orders_history([])

    assert "don't have any past orders yet" in text
    assert len(keyboard) == 2
    assert keyboard[0][0].callback_data == "back_catalog"
    assert "Browse Catalog" in keyboard[0][0].text
    assert keyboard[1][0].callback_data == "back_start"


def test_render_orders_history_with_two_orders():
    """Two orders produce 4 keyboard rows with status emojis."""
    orders = [
        {"id": 101, "total_amount": "49.99", "status": "PENDING"},
        {"id": 202, "total_amount": "125.00", "status": "COMPLETED"},
    ]

    text, keyboard = render_orders_history(orders)

    # Text assertions
    assert "Your Purchase History" in text
    assert "Page 1 of 1" in text

    # Button count: 4 rows (2 order buttons + 1 pagination row + 1 back button)
    assert len(keyboard) == 4

    # Pagination row (single page, empty)
    assert len(keyboard[2]) == 0

    # Order button assertions: now includes status emoji
    assert "Order #101" in keyboard[0][0].text
    assert "49.99" in keyboard[0][0].text
    assert "🟡" in keyboard[0][0].text
    assert "(Pending" in keyboard[0][0].text
    assert keyboard[0][0].callback_data == "view_old_order_101"

    assert "Order #202" in keyboard[1][0].text
    assert "125.00" in keyboard[1][0].text
    assert "🟢" in keyboard[1][0].text
    assert "(Completed" in keyboard[1][0].text
    assert keyboard[1][0].callback_data == "view_old_order_202"

    # Back button assertion
    assert "Back to Main Menu" in keyboard[3][0].text
    assert keyboard[3][0].callback_data == "back_start"


def test_render_orders_history_pagination():
    """10 orders: page 1 shows 5 + Next, page 2 shows 5 + Prev."""
    orders = [
        {"id": i, "total_amount": f"{i * 10}.00", "status": "PENDING"}
        for i in range(1, 11)
    ]

    # Page 1: first 5 orders + Next button + Back button
    text, keyboard = render_orders_history(orders, page=1)
    assert "Your Purchase History" in text
    assert "Page 1 of 2" in text
    assert len(keyboard) == 7  # 5 order rows + 1 pagination row + 1 back button

    # Order buttons show correct IDs
    assert "Order #1" in keyboard[0][0].text
    assert "Order #5" in keyboard[4][0].text

    # Pagination row: Next button only
    pagination_row = keyboard[5]
    assert len(pagination_row) == 1
    assert "Next" in pagination_row[0].text
    assert "➡️" in pagination_row[0].text
    assert pagination_row[0].callback_data == "view_history_p_2"

    # Back button
    assert keyboard[6][0].callback_data == "back_start"

    # Page 2: last 5 orders + Prev button + Back button
    text, keyboard = render_orders_history(orders, page=2)
    assert "Your Purchase History" in text
    assert "Page 2 of 2" in text
    assert len(keyboard) == 7  # 5 order rows + 1 pagination row + 1 back button

    # Order buttons show correct IDs
    assert "Order #6" in keyboard[0][0].text
    assert "Order #10" in keyboard[4][0].text

    # Pagination row: Prev button only
    pagination_row = keyboard[5]
    assert len(pagination_row) == 1
    assert "Prev" in pagination_row[0].text
    assert "⬅️" in pagination_row[0].text
    assert pagination_row[0].callback_data == "view_history_p_1"

    # Back button
    assert keyboard[6][0].callback_data == "back_start"


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


def test_render_welcome_dashboard_with_cart_and_order():
    """Scenario 4: A user with both an active cart and a recent order."""
    sample_cart = {
        "items": [{"product_name": "Widget", "quantity": 2}],
        "cart_total": "50.00",
    }
    sample_order = {
        "id": 99,
        "status": "COMPLETED",
    }

    text, keyboard = render_welcome_dashboard(
        user_name="Diana",
        cart=sample_cart,
        latest_order=sample_order,
    )

    assert "Welcome back, Diana!" in text
    assert "Active Cart" in text
    assert "2 items" in text
    assert "50.00" in text
    assert "Order #99" in text
    assert "[Completed/Paid]" in text

    # Keyboard: Browse Catalog + View Active Cart + Order History
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "📦 Browse Catalog"
    assert keyboard[1][0].text == "🛍️ View Active Cart"
    assert keyboard[1][0].callback_data == "view_cart_nav"
    assert keyboard[2][0].text == "📜 Order History"
    assert keyboard[2][0].callback_data == "view_history_nav"


def test_extract_user_context_from_private_chat():
    """extract_user_context returns a clean dict of Telegram user fields."""
    from handlers.common import extract_user_context

    update = MagicMock()
    update.effective_user.id = 42
    update.effective_user.username = "alice"
    update.effective_user.first_name = "Alice"
    update.effective_user.last_name = "Smith"

    result = extract_user_context(update)
    assert result == {
        "telegram_id": 42,
        "username": "alice",
        "first_name": "Alice",
        "last_name": "Smith",
    }


# ---- start / back_to_start (stateful — need app.bot_data["ctx"]) --------


def _make_start_update():
    """Build a minimial Update surrogate with the fields ``start`` reads."""
    update = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Test"
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_chat.id = 456
    # Provide a mock message so the footprint-eviction path can run
    update.message = MagicMock()
    update.message.delete = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_start_creates_new_canvas_when_none_exists(context_with_app):
    """Test 1 – Pristine Generation: no active_menu_id → send_message."""
    context_with_app.user_data = {}  # no active_menu_id
    context_with_app.bot.edit_message_text = AsyncMock()
    context_with_app.bot.send_message = AsyncMock()  # not used by handler

    update = _make_start_update()
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 404

    await start(update, context_with_app)

    # Should have deleted the incoming /start message
    update.message.delete.assert_called_once()

    # Should have sent a *new* message (no edit attempt since no active_menu_id)
    update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 404

    # User should be synced into the mock API
    ctx = context_with_app.application.bot_data["ctx"]
    assert 123 in ctx.api.users

    # The dashboard text should include the expected welcome content
    call_kwargs = update.effective_chat.send_message.call_args[1]
    assert "Welcome back, Test!" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_start_edits_existing_canvas(context_with_app):
    """Test 2 – Smooth Mutation: active_menu_id set → edit_message_text."""
    context_with_app.user_data = {"active_menu_id": 777}
    context_with_app.bot.edit_message_text = AsyncMock()

    update = _make_start_update()
    # send_message should NOT be called — only edit_message_text
    update.effective_chat.send_message = AsyncMock()

    await start(update, context_with_app)

    # The incoming message should still be deleted
    update.message.delete.assert_called_once()

    # Should edit the existing canvas instead of sending a new message
    context_with_app.bot.edit_message_text.assert_called_once()
    call_kwargs = context_with_app.bot.edit_message_text.call_args[1]
    assert call_kwargs["message_id"] == 777
    assert "Welcome back, Test!" in call_kwargs["text"]

    # Should NOT have sent a brand new message
    update.effective_chat.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_start_heals_when_canvas_is_missing(context_with_app):
    """Test 3 – Structural Self-Healing: edit raises → fall back to send."""
    context_with_app.user_data = {"active_menu_id": 777}
    # Simulate a deleted/expired canvas
    context_with_app.bot.edit_message_text = AsyncMock(
        side_effect=Exception("Message to edit not found")
    )

    update = _make_start_update()
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 808

    await start(update, context_with_app)

    # Should have attempted the edit
    context_with_app.bot.edit_message_text.assert_called_once()
    edit_kwargs = context_with_app.bot.edit_message_text.call_args[1]
    assert edit_kwargs["message_id"] == 777

    # Exception should have been caught — should fall back to send_message
    update.effective_chat.send_message.assert_called_once()
    send_kwargs = update.effective_chat.send_message.call_args[1]
    assert "Welcome back, Test!" in send_kwargs["text"]

    # New message ID should be stored
    assert context_with_app.user_data["active_menu_id"] == 808


@pytest.mark.asyncio
async def test_back_to_start_edits_message(context_with_app):
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.callback_query.from_user.first_name = "Test"
    context = context_with_app

    await back_to_start(update, context)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()

    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "Welcome back, Test!" in call_args["text"]
