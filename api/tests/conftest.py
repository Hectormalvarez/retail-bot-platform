import pytest
from rest_framework.test import APIClient
from .factories import CartFactory, CategoryFactory, ProductFactory, TelegramUserFactory


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