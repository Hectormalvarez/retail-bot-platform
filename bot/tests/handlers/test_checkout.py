from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from api_client import MockApiClient
from handlers.checkout import (
    ASK_SAVE_ADDRESS,
    CONFIRMING,
    SELECTING_ADDRESS,
    WAITING_FOR_ADDRESS,
    build_address_keyboard,
    cancel_checkout,
    cancel_command_fallback,
    capture_address,
    compute_address_label,
    finalize_order,
    pick_saved_address,
    prompt_new_address,
    render_order_confirmation,
    render_order_receipt,
    save_address_and_confirm,
    skip_save_confirm,
    start_checkout,
    view_history_handler,
)

# ---- pure helpers (no DI needed) ----------------------------------------


def test_render_order_confirmation():
    """Verifies the order confirmation preview text and keyboard layout."""
    cart = {
        "items": [{"product_name": "Mug", "quantity": 2, "subtotal": "30.00"}],
        "cart_total": "30.00",
    }
    text, keyboard = render_order_confirmation(cart, "123 Main St")

    assert "Confirm Your Order Selection" in text
    assert "123 Main St" in text
    assert "Mug" in text
    assert "30.00" in text
    assert len(keyboard) == 2
    assert keyboard[0][0].callback_data == "confirm_checkout"
    assert keyboard[1][0].callback_data == "cancel_checkout"


def test_render_order_receipt():
    """Verifies the completed order receipt text after checkout."""
    order_data = {
        "id": 42,
        "items": [
            {"product_name": "T-Shirt", "quantity": 1, "price_at_purchase": "25.00"}
        ],
        "total_amount": "25.00",
    }
    text, keyboard = render_order_receipt(order_data, "456 Side St")

    assert "Order #42 Confirmed" in text
    assert "456 Side St" in text
    assert "T-Shirt" in text
    assert "25.00" in text
    assert keyboard == []


def test_build_address_keyboard():
    """build_address_keyboard creates correct buttons from address list."""
    addresses = [
        {"id": 1, "label": "Home", "full_address": "123 Main St, City"},
        {"id": 2, "label": "Office", "full_address": "456 Work Ave, Town"},
    ]
    keyboard = build_address_keyboard(addresses)
    assert len(keyboard) == 4  # 2 addresses + "new address" + "cancel"
    assert keyboard[0][0].callback_data == "pick_addr_1"
    assert keyboard[1][0].callback_data == "pick_addr_2"
    assert keyboard[2][0].callback_data == "new_address"
    assert keyboard[3][0].callback_data == "cancel_checkout"


def test_compute_address_label():
    """compute_address_label generates sequential labels."""
    assert compute_address_label([]) == "Address #1"
    assert compute_address_label([{"id": 1}]) == "Address #2"
    assert compute_address_label([{"id": 1}, {"id": 2}]) == "Address #3"


# ---- view_history_handler tests -----------------------------------------


def _make_context(api=None):
    """Helper: build a mock context wired to a MockApiClient."""
    if api is None:
        api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}
    ctx = MagicMock()
    ctx.application = ctx_app
    ctx.user_data = {}
    return ctx


@pytest.mark.asyncio
async def test_view_history_handler_with_no_orders():
    """view_history_handler shows 'no past orders' when no orders exist."""
    api = MockApiClient()
    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    await view_history_handler(update, ctx)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()

    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "You have no past orders yet" in call_args["text"]
    assert call_args["parse_mode"] == "Markdown"
    assert call_args["reply_markup"] is None


@pytest.mark.asyncio
async def test_view_history_handler_with_orders():
    """view_history_handler fetches orders and renders order history menu."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "Widget", "price": "9.99"}}
    )
    # Pre-populate orders via the checkout flow
    await api.add_product_to_cart(123, 1)
    await api.submit_order(123, "123 Main St")
    await api.add_product_to_cart(123, 1)
    await api.submit_order(123, "456 Oak Ave")

    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    await view_history_handler(update, ctx)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()

    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "Your Past Orders" in call_args["text"]

    reply_markup = call_args["reply_markup"]
    assert reply_markup is not None

    # The inline keyboard should have 3 rows: 2 orders + 1 back button
    assert len(reply_markup.inline_keyboard) == 3
    assert "Order #1" in reply_markup.inline_keyboard[0][0].text
    assert "Order #2" in reply_markup.inline_keyboard[1][0].text
    assert "Back to Main Menu" in reply_markup.inline_keyboard[2][0].text


# ---- handlers that need app.bot_data["ctx"] ------------------------------


@pytest.mark.asyncio
async def test_start_checkout_with_empty_cart_aborts():
    """start_checkout returns END when the cart has no items."""
    api = MockApiClient()
    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await start_checkout(update, ctx)

    assert state == ConversationHandler.END
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_start_checkout_with_items_no_addresses_asks_text():
    """Transitions to WAITING_FOR_ADDRESS when cart has items but no saved addresses."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await start_checkout(update, ctx)

    assert state == WAITING_FOR_ADDRESS
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_start_checkout_with_saved_addresses_shows_selection():
    """Transitions to SELECTING_ADDRESS when cart has items + saved addresses exist."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    await api.create_address(123, "Home", "123 Main St")
    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await start_checkout(update, ctx)

    assert state == SELECTING_ADDRESS
    assert len(ctx.user_data["saved_addresses"]) == 1
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_pick_saved_address_transitions_to_confirming():
    """pick_saved_address looks up the selected address and shows confirmation."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    await api.create_address(123, "Home", "123 Main St")
    ctx = _make_context(api)

    # Pre-populate saved_addresses from what start_checkout would have done
    ctx.user_data["saved_addresses"] = await api.fetch_addresses(123)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.callback_query.data = "pick_addr_1"

    state = await pick_saved_address(update, ctx)

    assert state == CONFIRMING
    assert ctx.user_data["checkout_address"] == "123 Main St"
    assert ctx.user_data["address_was_saved"] is True
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_pick_saved_address_invalid_id_returns_end():
    """pick_saved_address returns END when the address id is not found."""
    api = MockApiClient()
    ctx = _make_context(api)
    ctx.user_data["saved_addresses"] = []

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.callback_query.data = "pick_addr_999"

    state = await pick_saved_address(update, ctx)

    assert state == ConversationHandler.END


@pytest.mark.asyncio
async def test_prompt_new_address():
    """prompt_new_address transitions to WAITING_FOR_ADDRESS."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await prompt_new_address(update, MagicMock())

    assert state == WAITING_FOR_ADDRESS
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_capture_address_transitions_to_ask_save():
    """capture_address stores address and prompts to save."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)

    update = MagicMock()
    update.message.text = "123 Main St"
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 999
    update.effective_user.id = 123

    state = await capture_address(update, ctx)

    assert ctx.user_data["checkout_address"] == "123 Main St"
    assert ctx.user_data["address_was_saved"] is False
    assert ctx.user_data["active_menu_id"] == 999
    assert state == ASK_SAVE_ADDRESS


@pytest.mark.asyncio
async def test_save_address_and_confirm():
    """save_address_and_confirm persists address and shows confirmation."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)
    ctx.user_data["checkout_address"] = "456 Oak Ln"

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await save_address_and_confirm(update, ctx)

    assert state == CONFIRMING
    assert ctx.user_data["address_was_saved"] is True
    # Verify the address was actually persisted
    addresses = await api.fetch_addresses(123)
    assert len(addresses) == 1
    assert addresses[0]["full_address"] == "456 Oak Ln"
    assert addresses[0]["label"] == "Address #1"


@pytest.mark.asyncio
async def test_skip_save_confirm():
    """skip_save_confirm goes straight to confirmation without saving."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "T-Shirt", "price": "25.00"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)
    ctx.user_data["checkout_address"] = "789 Pine Rd"

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123

    state = await skip_save_confirm(update, ctx)

    assert state == CONFIRMING
    # Verify address was NOT persisted
    addresses = await api.fetch_addresses(123)
    assert addresses == []


@pytest.mark.asyncio
async def test_finalize_order_removes_keyboard_immediately():
    """finalize_order strips inline keyboard at start to prevent double-clicks."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "Widget", "price": "9.99"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)
    ctx.user_data["checkout_address"] = "123 Main St"

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.effective_chat.send_message = AsyncMock()

    await finalize_order(update, ctx)

    # Assert the reply markup was stripped at the beginning
    update.callback_query.edit_message_reply_markup.assert_called_once_with(
        reply_markup=None
    )


@pytest.mark.asyncio
async def test_finalize_order_success():
    """finalize_order submits order and returns END."""
    api = MockApiClient(
        product_details={1: {"id": 1, "name": "Widget", "price": "9.99"}}
    )
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)
    ctx.user_data["checkout_address"] = "123 Main St"

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.effective_chat.send_message = AsyncMock()

    state = await finalize_order(update, ctx)

    assert state == ConversationHandler.END
    update.effective_chat.send_message.assert_called_once()
    call_args = update.effective_chat.send_message.call_args[1]
    assert "Order #1 Confirmed" in call_args["text"]


@pytest.mark.asyncio
async def test_finalize_order_failure_shows_error():
    """finalize_order shows error message when order submission fails."""
    api = MockApiClient()  # no products → submit_order returns None
    ctx = _make_context(api)
    ctx.user_data["checkout_address"] = "123 Main St"

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.effective_chat.send_message = AsyncMock()

    state = await finalize_order(update, ctx)

    assert state == ConversationHandler.END
    update.effective_chat.send_message.assert_called_once()
    call_args = update.effective_chat.send_message.call_args[1]
    assert "Checkout Failed" in call_args["text"]
    assert "checkout_address" not in ctx.user_data


@pytest.mark.asyncio
async def test_cancel_checkout_renders_cart():
    """cancel_checkout returns to the cart view."""
    api = MockApiClient()
    await api.add_product_to_cart(123, 1)
    ctx = _make_context(api)

    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = 123
    update.callback_query.message.edit_text = AsyncMock()

    state = await cancel_checkout(update, ctx)

    assert state == ConversationHandler.END
    update.callback_query.answer.assert_called_once_with(text="Checkout aborted.")
    update.callback_query.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_command_fallback_sends_message():
    """cancel_command_fallback sends a cancellation message."""
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.application = MagicMock()
    ctx.application.bot_data = {"ctx": MagicMock(api=MockApiClient())}

    update = MagicMock()
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 500

    state = await cancel_command_fallback(update, ctx)

    assert state == ConversationHandler.END
    update.effective_chat.send_message.assert_called_once()
    assert ctx.user_data["active_menu_id"] == 500
