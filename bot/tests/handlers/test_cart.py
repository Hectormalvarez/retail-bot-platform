from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_client import MockApiClient
from handlers.cart import (
    add_to_cart_handler,
    adjust_quantity_handler,
    cart_command,
    parse_quantity_action,
    render_cart_menu,
)

# ---- pure helpers (no DI needed) ----------------------------------------


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


# ---- handlers that need app.bot_data["ctx"] ------------------------------


@pytest.mark.asyncio
async def test_add_to_cart_handler_answers_callback():
    """add_to_cart_handler uses DI to add product and answers callback."""
    mock_update = MagicMock()
    mock_update.callback_query.data = "add_to_cart_5"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()

    # Wire up a context with a MockApiClient that has the product
    api = MockApiClient(
        product_details={
            5: {
                "id": 5,
                "name": "Test Widget",
                "price": "19.99",
                "category_name": "Widgets",
                "stock": 10,
                "description": "A widget",
            }
        }
    )
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    await add_to_cart_handler(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_add_to_cart_handler_failure_shows_error():
    """add_to_cart_handler answers with error when API returns False."""
    AM, MM = AsyncMock, MagicMock

    mock_update = MM()
    mock_update.callback_query.data = "add_to_cart_999"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AM()

    # Build an API mock that returns failure
    api = MockApiClient()
    # Patch fetch_user_cart to return None → add_product_to_cart returns False
    api.fetch_user_cart = AM(return_value=None)  # type: ignore

    ctx_app = MM()
    ctx_app.bot_data = {"ctx": MM(api=api)}

    ctx = MM()
    ctx.application = ctx_app

    await add_to_cart_handler(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()
    args, kwargs = mock_update.callback_query.answer.call_args
    text = kwargs.get("text", args[0] if args else "")
    assert "Could not modify cart" in text


@pytest.mark.asyncio
async def test_cart_command_sends_new_message(context_with_app):
    """cart_command (command path) sends a new message via DI."""
    mock_update = MagicMock()
    mock_update.callback_query = None
    mock_update.effective_user.id = 123
    mock_update.effective_chat.send_message = AsyncMock()
    mock_update.effective_chat.send_message.return_value.message_id = 200

    from handlers.cart import cart_command

    with patch("handlers.cart.clear_chat_footprint", AsyncMock()):
        await cart_command(mock_update, context_with_app)

    mock_update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 200


@pytest.mark.asyncio
async def test_cart_command_edits_message():
    """cart_command (callback path) edits the existing message."""
    api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    mock_update = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message.edit_text = AsyncMock()
    mock_update.effective_user.id = 123

    await cart_command(mock_update, ctx)

    mock_update.callback_query.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_adjust_quantity_handler_edits_message():
    """adjust_quantity_handler edits the message after quantity change."""
    api = MockApiClient(
        product_details={
            5: {"id": 5, "name": "Widget", "price": "9.99"},
        }
    )
    # Pre-populate a cart
    await api.add_product_to_cart(123, 5)

    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    mock_update = MagicMock()
    mock_update.callback_query.data = "qty_up_1_1"
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.message.edit_text = AsyncMock()
    mock_update.effective_user.id = 123

    await adjust_quantity_handler(mock_update, ctx)

    mock_update.callback_query.message.edit_text.assert_called_once()
