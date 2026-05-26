from unittest.mock import AsyncMock, patch

import pytest

from handlers.cart import parse_quantity_action, render_cart_menu


def test_render_cart_menu_empty():
    text, keyboard = render_cart_menu(None)
    assert "Your Shopping Cart is Empty" in text
    assert len(keyboard) == 1
    assert keyboard[0][0].callback_data == "back_catalog"


def test_render_cart_menu_with_items():
    mock_cart = {
        "items": [
            {
                "id": 1,
                "product_name": "Cyberpunk Mug",
                "quantity": 2,
                "subtotal": "40.00",
                "product": 5,
            }
        ],
        "cart_total": "40.00",
    }

    text, keyboard = render_cart_menu(mock_cart)

    assert "Cyberpunk Mug" in text
    assert "40.00" in text
    # Verify the keyboard structure:
    # Row 1: Item buttons (➖, Name, ➕)
    # Row 2: Proceed to Checkout
    # Row 3: Keep Shopping
    assert len(keyboard) == 3
    assert keyboard[0][1].text == "Cyberpunk Mug"
    assert keyboard[0][1].callback_data == "view_prod_5"


def test_parse_quantity_action_down():
    """Verifies that a qty_down callback string is correctly parsed."""
    action, item_id, quantity = parse_quantity_action("qty_down_3_5")
    assert action == "down"
    assert item_id == 3
    assert quantity == 5


def test_parse_quantity_action_up():
    """Verifies that a qty_up callback string is correctly parsed."""
    action, item_id, quantity = parse_quantity_action("qty_up_7_2")
    assert action == "up"
    assert item_id == 7
    assert quantity == 2


@pytest.mark.asyncio
async def test_add_to_cart_handler_answers_callback(mock_update):
    """Smoke: add_to_cart_handler answers the callback query."""
    mock_update.callback_query.data = "add_to_cart_5"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()

    from handlers.cart import add_to_cart_handler

    with patch("handlers.cart.add_product_to_cart", return_value=True):
        await add_to_cart_handler(mock_update, None)

    mock_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cart_command_sends_new_message(mock_update, mock_context):
    """Smoke: cart_command (command path) sends a new message."""
    mock_update.callback_query = None
    mock_update.effective_user.id = 123
    mock_update.effective_chat.send_message = AsyncMock()
    mock_update.effective_chat.send_message.return_value.message_id = 200

    mock_cart = {"items": [], "cart_total": "0.00"}

    from handlers.cart import cart_command

    with (
        patch("handlers.cart.fetch_user_cart", return_value=mock_cart),
        patch("handlers.cart.clear_chat_footprint", new_callable=AsyncMock),
    ):
        await cart_command(mock_update, mock_context)

    mock_update.effective_chat.send_message.assert_called_once()
    assert mock_context.user_data["active_menu_id"] == 200


@pytest.mark.asyncio
async def test_cart_command_edits_message(mock_update):
    """Smoke: cart_command (callback path) edits the existing message."""
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message.edit_text = AsyncMock()

    mock_cart = {"items": [], "cart_total": "0.00"}

    from handlers.cart import cart_command

    with patch("handlers.cart.fetch_user_cart", return_value=mock_cart):
        await cart_command(mock_update, None)

    mock_update.callback_query.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_adjust_quantity_handler_edits_message(mock_update):
    """Smoke: adjust_quantity_handler edits the message after quantity change."""
    mock_update.callback_query.data = "qty_up_3_1"
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message.edit_text = AsyncMock()
    mock_update.effective_user.id = 123

    mock_cart = {"items": [], "cart_total": "0.00"}

    from handlers.cart import adjust_quantity_handler

    with (
        patch("handlers.cart.update_item_quantity", return_value=True),
        patch("handlers.cart.fetch_user_cart", return_value=mock_cart),
    ):
        await adjust_quantity_handler(mock_update, None)

    mock_update.callback_query.message.edit_text.assert_called_once()