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
