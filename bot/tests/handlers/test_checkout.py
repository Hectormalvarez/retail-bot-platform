from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from handlers.checkout import (
    CONFIRMING,
    WAITING_FOR_ADDRESS,
    cancel_checkout,
    cancel_command_fallback,
    capture_address,
    finalize_order,
    render_order_confirmation,
    render_order_receipt,
    start_checkout,
)

from api_client import MockApiClient


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


# ---- handlers that need app.bot_data["ctx"] ------------------------------


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
async def test_start_checkout_with_items_asks_address():
    """start_checkout transitions to WAITING_FOR_ADDRESS when cart has items."""
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
async def test_capture_address_transitions_to_confirming():
    """capture_address stores address, fetches cart via DI, and returns CONFIRMING."""
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
    assert ctx.user_data["active_menu_id"] == 999
    assert state == CONFIRMING


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