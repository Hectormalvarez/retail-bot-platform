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
