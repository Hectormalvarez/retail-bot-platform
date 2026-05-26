from unittest.mock import AsyncMock, patch

import pytest

from handlers.catalog import parse_product_id, render_catalog_menu, render_product_card


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


def test_parse_product_id():
    """Verifies that a callback_data string is split correctly into an integer ID."""
    assert parse_product_id("view_prod_42") == 42
    assert parse_product_id("add_to_cart_7") == 7
    assert parse_product_id("qty_up_10_3") == 3


@pytest.mark.asyncio
async def test_catalog_command_sends_new_message(mock_update, mock_context):
    """Smoke: catalog_command sends a new message via send_message."""
    mock_update.callback_query = None
    mock_update.effective_chat.send_message = AsyncMock()
    mock_update.effective_chat.send_message.return_value.message_id = 100

    from handlers.catalog import catalog_command

    with (
        patch("handlers.catalog.fetch_products", return_value=[]),
        patch("handlers.catalog.clear_chat_footprint", new_callable=AsyncMock),
    ):
        await catalog_command(mock_update, mock_context)

    mock_update.effective_chat.send_message.assert_called_once()
    assert mock_context.user_data["active_menu_id"] == 100


@pytest.mark.asyncio
async def test_view_product_detail_edits_message(mock_update):
    """Smoke: view_product_detail edits the existing message."""
    mock_update.callback_query.data = "view_prod_1"
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    mock_product = {
        "id": 1,
        "name": "Test",
        "category_name": "Gear",
        "price": "10.00",
        "stock": 5,
        "description": "desc",
    }

    from handlers.catalog import view_product_detail

    with patch("handlers.catalog.fetch_product_detail", return_value=mock_product):
        await view_product_detail(mock_update, None)

    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_back_to_catalog_edits_message(mock_update):
    """Smoke: back_to_catalog edits the existing message."""
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    from handlers.catalog import back_to_catalog

    with patch("handlers.catalog.fetch_products", return_value=[]):
        await back_to_catalog(mock_update, None)

    mock_update.callback_query.edit_message_text.assert_called_once()