from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from handlers.checkout import (
    CONFIRMING,
    WAITING_FOR_ADDRESS,
    capture_address,
    start_checkout,
)


@pytest.mark.asyncio
async def test_start_checkout_with_empty_cart_aborts(mocker):
    mocker.patch("handlers.checkout.fetch_user_cart", return_value={"items": []})

    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    state = await start_checkout(update, context)

    assert state == ConversationHandler.END
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_start_checkout_with_items_asks_address(mocker):
    mocker.patch(
        "handlers.checkout.fetch_user_cart", return_value={"items": [{"id": 1}]}
    )

    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    state = await start_checkout(update, context)

    assert state == WAITING_FOR_ADDRESS
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_capture_address_transitions_to_confirming(mocker):
    mocker.patch("handlers.checkout.clear_chat_footprint", new_callable=AsyncMock)
    mocker.patch(
        "handlers.checkout.fetch_user_cart",
        return_value={
            "items": [{"product_name": "T-Shirt", "quantity": 1, "subtotal": "25.00"}],
            "cart_total": "25.00",
        },
    )

    update = MagicMock()
    update.message.text = "123 Main St"
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 999

    context = MagicMock()
    context.user_data = {}

    state = await capture_address(update, context)

    assert context.user_data["checkout_address"] == "123 Main St"
    assert context.user_data["active_menu_id"] == 999
    assert state == CONFIRMING
