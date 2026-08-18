"""Pure unit tests for service layer — zero database calls."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock, MagicMock

from store.cart_service import CartService
from store.repositories import (
    DjangoCartRepo,
    DjangoOrderRepo,
    DjangoProductRepo,
    DjangoUserRepo,
)
from store.services import OrderService


# ---------------------------------------------------------------------------
# OrderService tests
# ---------------------------------------------------------------------------


def _make_service(mocks: dict | None = None) -> OrderService:
    """Build an OrderService with all mocked repos (or defaults)."""
    defaults = {
        "user_repo": Mock(spec=DjangoUserRepo),
        "cart_repo": Mock(spec=DjangoCartRepo),
        "product_repo": Mock(spec=DjangoProductRepo),
        "order_repo": Mock(spec=DjangoOrderRepo),
    }
    if mocks:
        defaults.update(mocks)
    return OrderService(**defaults)


def test_create_order_empty_cart_returns_error():
    """Empty cart items -> (None, 'Shopping cart is empty')."""
    mock_user = MagicMock()
    mock_cart = MagicMock()
    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_by_user.return_value = mock_cart
    cart_repo.get_items.return_value = []  # empty cart

    service = _make_service({"user_repo": user_repo, "cart_repo": cart_repo})
    order, error = service.create_order(1, "addr")

    assert order is None
    assert error == "Shopping cart is empty"
    user_repo.get_by_telegram.assert_called_once_with(1)
    cart_repo.get_by_user.assert_called_once_with(mock_user)
    cart_repo.get_items.assert_called_once_with(mock_cart)


def test_create_order_invalid_user_returns_error():
    """Non-existent user -> (None, 'Invalid user')."""
    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.side_effect = Exception("User not found")

    service = _make_service({"user_repo": user_repo})
    order, error = service.create_order(999, "addr")

    assert order is None
    assert error is not None
    assert "Invalid user" in error


def test_create_order_insufficient_stock_returns_error():
    """Product stock < requested quantity -> (None, 'Insufficient stock')."""
    mock_user = MagicMock()
    mock_cart = MagicMock()
    mock_item = MagicMock()
    mock_item.product.id = 1
    mock_item.quantity = 5
    mock_item.product.name = "Widget"

    mock_product = MagicMock()
    mock_product.stock = 2  # less than 5
    mock_product.name = "Widget"

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_by_user.return_value = mock_cart
    cart_repo.get_items.return_value = [mock_item]
    product_repo = Mock(spec=DjangoProductRepo)
    product_repo.get_for_update.return_value = mock_product

    service = _make_service(
        {
            "user_repo": user_repo,
            "cart_repo": cart_repo,
            "product_repo": product_repo,
        }
    )
    order, error = service.create_order(1, "addr")

    assert order is None
    assert error is not None
    assert "Insufficient stock" in error
    assert "Widget" in error
    product_repo.get_for_update.assert_called_once_with(1)


def test_create_order_happy_path_creates_order_with_items():
    """Valid order -> order created with items, stock decremented, cart emptied."""
    mock_user = MagicMock()
    mock_cart = MagicMock()
    mock_item = MagicMock()
    mock_item.product.id = 1
    mock_item.quantity = 2
    mock_item.product.price = Decimal("15.00")
    mock_item.product.name = "Widget"

    mock_product = MagicMock()
    mock_product.stock = 10
    mock_product.price = Decimal("15.00")
    mock_product.name = "Widget"

    mock_order = MagicMock()
    mock_order.user = mock_user
    mock_order.status = "PENDING"

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_by_user.return_value = mock_cart
    cart_repo.get_items.return_value = [mock_item]
    product_repo = Mock(spec=DjangoProductRepo)
    product_repo.get_for_update.return_value = mock_product
    product_repo.get_by_id.return_value = mock_product
    order_repo = Mock(spec=DjangoOrderRepo)
    order_repo.create.return_value = mock_order

    service = _make_service(
        {
            "user_repo": user_repo,
            "cart_repo": cart_repo,
            "product_repo": product_repo,
            "order_repo": order_repo,
        }
    )
    order, error = service.create_order(1, "addr")

    assert error is None
    assert order is mock_order
    order_repo.create.assert_called_once_with(
        user=mock_user,
        total_amount=Decimal("30.00"),
        shipping_address="addr",
    )
    product_repo.decrement_stock.assert_called_once_with(mock_product, 2)
    order_repo.create_item.assert_called_once_with(
        order=mock_order,
        product=mock_item.product,
        quantity=2,
        price_at_purchase=Decimal("15.00"),
    )
    cart_repo.delete_items.assert_called_once_with(mock_cart)


def test_create_order_calculates_total_correctly():
    """Multiple items with different prices -> total is sum of price * quantity."""
    mock_user = MagicMock()
    mock_cart = MagicMock()

    # Use real objects with proper types for numerical comparisons
    class FakeProduct:
        def __init__(self, pid, price, name, stock=100):
            self.id = pid
            self.price = price
            self.name = name
            self.stock = stock

    prod1 = FakeProduct(1, Decimal("10.00"), "Cheap")
    prod2 = FakeProduct(2, Decimal("20.00"), "Pricy")

    item1 = MagicMock()
    item1.product = prod1
    item1.quantity = 2

    item2 = MagicMock()
    item2.product = prod2
    item2.quantity = 3

    mock_order = MagicMock()

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_by_user.return_value = mock_cart
    cart_repo.get_items.return_value = [item1, item2]
    product_repo = Mock(spec=DjangoProductRepo)

    def _get_for_update(pid):
        return prod1 if pid == 1 else prod2

    product_repo.get_for_update.side_effect = _get_for_update
    product_repo.get_by_id.side_effect = _get_for_update
    order_repo = Mock(spec=DjangoOrderRepo)
    order_repo.create.return_value = mock_order

    service = _make_service(
        {
            "user_repo": user_repo,
            "cart_repo": cart_repo,
            "product_repo": product_repo,
            "order_repo": order_repo,
        }
    )
    order, error = service.create_order(1, "addr")

    assert error is None
    order_repo.create.assert_called_once()
    # total = 10*2 + 20*3 = 80
    assert order_repo.create.call_args[1]["total_amount"] == Decimal("80.00")


# ---------------------------------------------------------------------------
# CartService tests
# ---------------------------------------------------------------------------


def _make_cart_service(mocks: dict | None = None) -> CartService:
    """Build a CartService with all mocked repos (or defaults)."""
    defaults = {
        "user_repo": Mock(spec=DjangoUserRepo),
        "cart_repo": Mock(spec=DjangoCartRepo),
        "product_repo": Mock(spec=DjangoProductRepo),
    }
    if mocks:
        defaults.update(mocks)
    return CartService(**defaults)


def test_cart_add_new_item():
    """Adding a product not already in cart -> cart_repo.add_item called with quantity=1."""
    mock_user = MagicMock()
    mock_cart = MagicMock()

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_or_create.return_value = mock_cart
    cart_repo.find_item.return_value = None  # not in cart
    product_repo = Mock(spec=DjangoProductRepo)
    mock_product = MagicMock()
    product_repo.get_by_id.return_value = mock_product

    service = _make_cart_service(
        {
            "user_repo": user_repo,
            "cart_repo": cart_repo,
            "product_repo": product_repo,
        }
    )
    result = service.add_or_increment(1, 42)

    assert result is not None
    cart_repo.get_or_create.assert_called_once_with(mock_user)
    cart_repo.find_item.assert_called_once_with(mock_cart, 42)
    cart_repo.add_item.assert_called_once_with(mock_cart, mock_product, quantity=1)


def test_cart_add_existing_item_increments():
    """Adding a product already in cart -> increment_item_by called, no new item."""
    mock_user = MagicMock()
    mock_cart = MagicMock()
    mock_existing = MagicMock()

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_or_create.return_value = mock_cart
    cart_repo.find_item.return_value = mock_existing

    service = _make_cart_service({"user_repo": user_repo, "cart_repo": cart_repo})
    result = service.add_or_increment(1, 42)

    assert result is mock_existing
    cart_repo.increment_item_by.assert_called_once_with(mock_existing, 1)
    cart_repo.add_item.assert_not_called()


def test_cart_add_existing_item_bulk_increment_is_o1():
    """Adding quantity > 1 to an existing cart item uses a single bulk update."""
    mock_user = MagicMock()
    mock_cart = MagicMock()
    mock_existing = MagicMock()

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_or_create.return_value = mock_cart
    cart_repo.find_item.return_value = mock_existing

    service = _make_cart_service({"user_repo": user_repo, "cart_repo": cart_repo})
    result = service.add_or_increment(1, 42, quantity=5000)

    assert result is mock_existing
    cart_repo.increment_item_by.assert_called_once_with(mock_existing, 5000)
    cart_repo.increment_item.assert_not_called()


def test_cart_add_invalid_user_returns_none():
    """Adding with non-existent user -> returns None."""
    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.side_effect = Exception("User not found")

    service = _make_cart_service({"user_repo": user_repo})
    result = service.add_or_increment(999, 42)

    assert result is None


def test_cart_add_invalid_product_returns_none():
    """Adding with non-existent product -> returns None."""
    mock_user = MagicMock()
    mock_cart = MagicMock()

    user_repo = Mock(spec=DjangoUserRepo)
    user_repo.get_by_telegram.return_value = mock_user
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_or_create.return_value = mock_cart
    cart_repo.find_item.return_value = None
    product_repo = Mock(spec=DjangoProductRepo)
    product_repo.get_by_id.side_effect = Exception("Product not found")

    service = _make_cart_service(
        {
            "user_repo": user_repo,
            "cart_repo": cart_repo,
            "product_repo": product_repo,
        }
    )
    result = service.add_or_increment(1, 99999)

    assert result is None


def test_cart_update_quantity_to_zero_deletes_item():
    """Updating quantity to 0 -> item deleted, returns None."""
    mock_item = MagicMock()

    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_item.return_value = mock_item

    service = _make_cart_service({"cart_repo": cart_repo})
    result = service.update_quantity(1, 0)

    assert result is None
    cart_repo.delete_item.assert_called_once_with(mock_item)
    cart_repo.update_item_quantity.assert_not_called()


def test_cart_update_quantity_positive():
    """Updating quantity to positive number -> update_item_quantity called."""
    mock_item = MagicMock()

    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_item.return_value = mock_item

    service = _make_cart_service({"cart_repo": cart_repo})
    result = service.update_quantity(1, 5)

    assert result is mock_item
    cart_repo.update_item_quantity.assert_called_once_with(mock_item, 5)
    cart_repo.delete_item.assert_not_called()


def test_cart_update_quantity_nonexistent_item_returns_none():
    """Updating quantity for non-existent item -> returns None."""
    cart_repo = Mock(spec=DjangoCartRepo)
    cart_repo.get_item.side_effect = Exception("CartItem not found")

    service = _make_cart_service({"cart_repo": cart_repo})
    result = service.update_quantity(999, 1)

    assert result is None
