import pytest
from rest_framework.test import APIClient
from .factories import (
    CartFactory,
    CartItemFactory,
    CategoryFactory,
    OrderFactory,
    ProductFactory,
    TelegramUserFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return TelegramUserFactory(telegram_id=999, first_name="Fixture User")


@pytest.fixture
def test_category(db):
    return CategoryFactory(name="Tech", slug="tech")


@pytest.fixture
def test_product(db, test_category):
    return ProductFactory(
        category=test_category, name="Fixture Product", price="100.00", stock=5
    )


@pytest.fixture
def test_cart(db, test_user):
    return CartFactory(user=test_user)


@pytest.fixture
def test_cart_item(db, test_cart, test_product):
    return CartItemFactory(cart=test_cart, product=test_product)


@pytest.fixture
def test_order(db, test_user):
    return OrderFactory(user=test_user, total_amount="100.00")


@pytest.fixture
def test_order_item(db, test_order, test_product):
    return OrderItemFactory(order=test_order, product=test_product)
