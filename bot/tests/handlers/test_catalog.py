from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import BadRequest

from handlers.catalog import (
    back_to_catalog,
    catalog_command,
    parse_product_id,
    render_catalog_menu,
    render_product_card,
    view_product_detail,
)

from api_client import MockApiClient


# ---- pure helpers (no DI needed) ----------------------------------------


def test_render_catalog_menu_empty():
    """Verifies that an empty products list returns a maintenance message."""
    text, keyboard = render_catalog_menu([])
    assert "empty" in text or "maintenance" in text
    assert len(keyboard) == 0


def test_render_catalog_menu_populated():
    """Verifies that a populated catalog lists products with correct navigation buttons."""
    mock_products = [{"id": 1, "name": "T-Shirt", "price": "25.00"}]
    text, keyboard = render_catalog_menu(mock_products)

    assert "Available Products" in text
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "T-Shirt — $25.00"
    assert keyboard[0][0].callback_data == "view_prod_1"


def test_render_product_card_missing():
    """Verifies that a missing product dictionary returns a clean error message."""
    text, keyboard = render_product_card(None)
    assert "could not be found" in text
    assert len(keyboard) == 0


def test_render_product_card_populated():
    """Verifies that a product record maps cleanly to a markdown block and controls."""
    mock_product = {
        "id": 5,
        "name": "Mug",
        "category_name": "Gear",
        "price": "15.00",
        "stock": 10,
        "description": "A cool mug.",
    }
    text, keyboard = render_product_card(mock_product)

    assert "Mug" in text
    assert "15.00" in text
    assert len(keyboard) == 3
    assert keyboard[0][0].callback_data == "add_to_cart_5"
    assert keyboard[0][0].text == "🛒 Add to Cart"  # default when no cart


def test_render_product_card_shows_quantity_when_in_cart():
    """When the product is already in the cart, show the quantity in the button."""
    mock_product = {"id": 3, "name": "Widget", "category_name": "Gear",
                    "price": "10.00", "stock": 5, "description": "A widget."}
    cart = {
        "items": [
            {"product": 1, "quantity": 2, "subtotal": "20.00"},
            {"product": 3, "quantity": 3, "subtotal": "30.00"},
            {"product": 7, "quantity": 1, "subtotal": "5.00"},
        ],
        "cart_total": "55.00",
    }

    text, keyboard = render_product_card(mock_product, cart)

    assert "Widget" in text
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "🛒 Add Another (3 in Cart)"
    assert keyboard[0][0].callback_data == "add_to_cart_3"


def test_render_product_card_shows_default_when_not_in_cart():
    """When the product is not in the cart, fall back to default Add to Cart."""
    mock_product = {"id": 9, "name": "Sticker", "category_name": "Gear",
                    "price": "2.50", "stock": 100, "description": "A sticker."}
    cart = {
        "items": [
            {"product": 1, "quantity": 2, "subtotal": "20.00"},
            {"product": 3, "quantity": 3, "subtotal": "30.00"},
        ],
        "cart_total": "50.00",
    }

    text, keyboard = render_product_card(mock_product, cart)

    assert "Sticker" in text
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "🛒 Add to Cart"
    assert keyboard[0][0].callback_data == "add_to_cart_9"


def test_parse_product_id():
    """Verifies that a callback_data string is split correctly into an integer ID."""
    assert parse_product_id("view_prod_42") == 42
    assert parse_product_id("add_to_cart_7") == 7
    assert parse_product_id("qty_up_10_3") == 3


# ---- handlers that need app.bot_data["ctx"] ------------------------------


@pytest.mark.asyncio
async def test_catalog_command_sends_new_message(
    mock_update, context_with_app
):
    """catalog_command fetches products via DI and sends a new message."""
    mock_update.callback_query = None
    mock_update.effective_chat.send_message = AsyncMock()
    mock_update.effective_chat.send_message.return_value.message_id = 100

    with patch("handlers.catalog.clear_chat_footprint", AsyncMock()):
        await catalog_command(mock_update, context_with_app)

    mock_update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 100


@pytest.mark.asyncio
async def test_view_product_detail_edits_message():
    """view_product_detail fetches product detail + cart and edits the message."""
    mock_update = MagicMock()
    mock_update.callback_query.data = "view_prod_1"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    api = MockApiClient(
        product_details={
            1: {
                "id": 1,
                "name": "Test",
                "category_name": "Gear",
                "price": "10.00",
                "stock": 5,
                "description": "desc",
            }
        }
    )
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    await view_product_detail(mock_update, ctx)

    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_back_to_catalog_edits_message():
    """back_to_catalog fetches products and edits the message."""
    mock_update = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    await back_to_catalog(mock_update, ctx)

    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_back_to_catalog_swallows_message_not_modified_exception():
    """BadRequest("Message is not modified") is caught silently."""
    mock_update = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock(
        side_effect=BadRequest(message="Message is not modified"),
    )

    api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    # Should complete without raising
    await back_to_catalog(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()
