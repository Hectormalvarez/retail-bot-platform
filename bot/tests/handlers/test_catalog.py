from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import BadRequest

from api_client import MockApiClient
from handlers.catalog import (
    navigate_catalog,
    parse_product_id,
    render_catalog_menu,
    render_product_card,
    view_product_detail,
)

# ---- pure helpers (no DI needed) ----------------------------------------


def test_render_catalog_menu_empty():
    """Verifies that an empty products list still renders a structured menu."""
    text, keyboard = render_catalog_menu([], [], page=1, current_cat_id=0)
    assert "Available Products" in text
    assert "Page 1 of 1" in text
    assert len(keyboard) == 3  # 1 cat row + 0 products + 0 pagination + 2 nav rows


def test_render_catalog_menu_populated():
    """Verifies a populated catalog lists products with pagination slicing."""
    mock_products = [
        {"id": i, "name": f"Product {i}", "price": f"{i}.00"} for i in range(1, 11)
    ]
    text, keyboard = render_catalog_menu(mock_products, [], page=1, current_cat_id=0)

    assert "Available Products" in text
    assert "Page 1 of 2" in text
    # 1 category row + 5 products + 1 pagination row + 2 nav rows = 9
    assert len(keyboard) == 9
    # First row is "All" button only (no categories)
    assert keyboard[0][0].text == "🟢 All"
    assert keyboard[0][0].callback_data == "nav_cat_0_p_1"
    # First product button
    assert keyboard[1][0].text == "Product 1 — $1.00"
    assert keyboard[1][0].callback_data == "view_prod_1"
    # Last product on page 1
    assert keyboard[5][0].text == "Product 5 — $5.00"
    assert keyboard[5][0].callback_data == "view_prod_5"
    # Next button should be present (page 1 of 2)
    assert keyboard[6][0].text == "Next ➡️"
    assert keyboard[6][0].callback_data == "nav_cat_0_p_2"


def test_render_catalog_menu_page_2():
    """Verifies page 2 shows remaining products with Prev button."""
    mock_products = [
        {"id": i, "name": f"Product {i}", "price": f"{i}.00"} for i in range(1, 11)
    ]
    text, keyboard = render_catalog_menu(mock_products, [], page=2, current_cat_id=0)

    assert "Page 2 of 2" in text
    # 1 category row + 5 products + 1 pagination row + 2 nav rows = 9
    assert len(keyboard) == 9
    # First product on page 2
    assert keyboard[1][0].text == "Product 6 — $6.00"
    assert keyboard[1][0].callback_data == "view_prod_6"
    # Last product on page 2
    assert keyboard[5][0].text == "Product 10 — $10.00"
    assert keyboard[5][0].callback_data == "view_prod_10"
    # Prev button should be present
    assert keyboard[6][0].text == "⬅️ Prev"
    assert keyboard[6][0].callback_data == "nav_cat_0_p_1"


def test_render_catalog_menu_with_categories():
    """Verifies the category filter ribbon renders correctly."""
    mock_categories = [
        {"id": 1, "name": "Gear"},
        {"id": 2, "name": "Apparel"},
        {"id": 3, "name": "Books"},
    ]
    mock_products = [{"id": 1, "name": "T-Shirt", "price": "25.00"}]
    text, keyboard = render_catalog_menu(
        mock_products, mock_categories, page=1, current_cat_id=1
    )

    assert "Viewing: Gear" in text
    assert "Page 1 of 1" in text
    # Category row: All + 3 categories
    assert len(keyboard[0]) == 4
    assert keyboard[0][0].text == "All"  # not selected
    assert keyboard[0][0].callback_data == "nav_cat_0_p_1"
    assert keyboard[0][1].text == "🟢 Gear"  # selected
    assert keyboard[0][1].callback_data == "nav_cat_1_p_1"
    assert keyboard[0][2].text == "Apparel"
    assert keyboard[0][3].text == "Books"


def test_render_catalog_menu_empty_products_with_categories():
    """When products list is empty but categories exist, still show filter ribbon."""
    mock_categories = [{"id": 1, "name": "Gear"}]
    text, keyboard = render_catalog_menu([], mock_categories, page=1, current_cat_id=0)
    assert "Available Products" in text
    assert "Page 1 of 1" in text
    # Category row with All + Gear (2 buttons) + 2 nav rows = 3 rows
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "🟢 All"
    assert keyboard[0][1].text == "Gear"


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
    mock_product = {
        "id": 3,
        "name": "Widget",
        "category_name": "Gear",
        "price": "10.00",
        "stock": 5,
        "description": "A widget.",
    }
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
    assert "Stock: 2 available" in text
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "🛒 Add Another (3 in Cart)"
    assert keyboard[0][0].callback_data == "add_to_cart_3"


def test_render_product_card_shows_default_when_not_in_cart():
    """When the product is not in the cart, fall back to default Add to Cart."""
    mock_product = {
        "id": 9,
        "name": "Sticker",
        "category_name": "Gear",
        "price": "2.50",
        "stock": 100,
        "description": "A sticker.",
    }
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
async def test_navigate_catalog_sends_new_message(mock_update, context_with_app):
    """navigate_catalog via /catalog command sends a new message."""
    mock_update.callback_query = None
    mock_update.effective_chat.send_message = AsyncMock()
    mock_update.effective_chat.send_message.return_value.message_id = 100

    with patch("handlers.catalog.clear_chat_footprint", AsyncMock()):
        await navigate_catalog(mock_update, context_with_app)

    mock_update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 100


@pytest.mark.asyncio
async def test_navigate_catalog_back_catalog_edits_message():
    """navigate_catalog via back_catalog callback edits the message."""
    mock_update = MagicMock()
    mock_update.callback_query.data = "back_catalog"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    await navigate_catalog(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_navigate_catalog_with_nav_cat_callback():
    """navigate_catalog via nav_cat callback parses cat_id and page."""
    mock_update = MagicMock()
    mock_update.callback_query.data = "nav_cat_2_p_3"
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    api = MockApiClient()
    ctx_app = MagicMock()
    ctx_app.bot_data = {"ctx": MagicMock(api=api)}

    ctx = MagicMock()
    ctx.application = ctx_app

    await navigate_catalog(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_navigate_catalog_swallows_message_not_modified():
    """BadRequest("Message is not modified") is caught silently."""
    mock_update = MagicMock()
    mock_update.callback_query.data = "back_catalog"
    mock_update.callback_query.from_user.id = 123
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
    await navigate_catalog(mock_update, ctx)

    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


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
